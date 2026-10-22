"""Offline synthetic ZIPs only; no actual native code is downloaded or executed."""
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import zipfile

from hope_archive.optional_runtime import RuntimeComponent, WORKER, safe_name
from hope_archive import optional_runtime, desktop_api


class Response(io.BytesIO):
    url = 'https://example.invalid/component.zip'


def fixture(files=None):
    files = files or {WORKER: b'synthetic worker', '_internal/model.onnx': b'synthetic model'}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in files.items(): bundle.writestr(name, data)
    data = output.getvalue()
    return data, dict(version='test-v1', url=Response.url, bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest(),
                     files={name: dict(bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
                            for name, value in files.items()})


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.data, self.catalog = fixture()
        self.runtime = RuntimeComponent(self.home, self.catalog)
        self.addCleanup(self.runtime.close)

    def install(self):
        with patch.object(optional_runtime, 'urlopen', return_value=Response(self.data)):
            self.runtime.start(True)
            self.runtime.thread.join(5)
        self.assertFalse(self.runtime.thread.is_alive())

    def test_status_and_decline_never_download(self):
        with patch.object(optional_runtime, 'urlopen') as download:
            self.assertFalse(self.runtime.status()['installed'])
            for confirmed in (False, None, 1, 'true'):
                with self.assertRaises(ValueError): self.runtime.start(confirmed)
            self.runtime.cancel()
            download.assert_not_called()

    def test_one_install_shared_and_offline_restart(self):
        self.install()
        self.assertTrue(self.runtime.status()['installed'])
        fresh = RuntimeComponent(self.home, self.catalog)
        with patch.object(optional_runtime, 'urlopen', side_effect=AssertionError('offline')):
            self.assertEqual(fresh.command(), self.runtime.command())
            self.assertTrue(fresh.start(True)['installed'])
        self.assertEqual(len(list(self.runtime.home.iterdir())), 1)

    def test_hash_failure_can_retry_without_partial_activation(self):
        self.catalog['sha256'] = '0'*64
        self.install()
        self.assertEqual(self.runtime.status()['state'], 'failed')
        self.assertFalse(self.runtime.target().exists())
        self.assertEqual(list(self.runtime.home.iterdir()), [])
        self.catalog['sha256'] = hashlib.sha256(self.data).hexdigest()
        self.install()
        self.assertTrue(self.runtime.status()['installed'])

    def test_corruption_refused_and_explicit_repair(self):
        self.install()
        (self.runtime.target() / WORKER).write_bytes(b'corrupt')
        self.assertFalse(self.runtime.status()['installed'])
        with self.assertRaises(ValueError): self.runtime.command()
        self.install()
        self.assertTrue(self.runtime.status()['installed'])

    def test_cancellation_cleans_staging(self):
        runtime = self.runtime
        class CancelledResponse(Response):
            def read(self, size=-1):
                runtime.cancel()
                return super().read(size)
        with patch.object(optional_runtime, 'urlopen', return_value=CancelledResponse(self.data)):
            runtime.start(True)
            runtime.thread.join(5)
        self.assertEqual(runtime.status()['state'], 'cancelled')
        self.assertFalse(runtime.target().exists())
        self.assertEqual(list(runtime.home.iterdir()), [])

    def test_simultaneous_consumers_start_only_one_download(self):
        entered, release = threading.Event(), threading.Event()
        def response(*args, **kwargs):
            entered.set()
            release.wait(3)
            return Response(self.data)
        with patch.object(optional_runtime, 'urlopen', side_effect=response) as download:
            self.runtime.start(True)
            self.assertTrue(entered.wait(2))
            self.runtime.start(True)
            release.set()
            self.runtime.thread.join(5)
            self.assertEqual(download.call_count, 1)

    def test_unsafe_archive_and_missing_file_are_rejected(self):
        for files in ({'../escape.exe': b'x'}, {WORKER: b'x', 'CON.txt': b'x'}, {WORKER: b'x'}):
            self.data, catalog = fixture(files)
            self.runtime.catalog = catalog
            if list(files) == [WORKER]:
                catalog['files']['missing.dll'] = dict(bytes=1, sha256='0'*64)
            self.install()
            self.assertFalse(self.runtime.target().exists())
        self.assertFalse((self.home / 'escape.exe').exists())
        for name in ('C:/x', '..\\x', '/x', 'a/../x', 'a/NUL', 'a/file.'):
            self.assertFalse(safe_name(name))

    def test_unpublished_catalog_does_not_fetch(self):
        runtime = RuntimeComponent(self.home, None)
        self.assertFalse(runtime.status()['available'])
        with self.assertRaises(ValueError): runtime.start(True)

    def test_network_failure_and_https_downgrade_never_activate(self):
        with patch.object(optional_runtime, 'urlopen', side_effect=TimeoutError):
            self.runtime.start(True)
            self.runtime.thread.join(5)
        self.assertFalse(self.runtime.status()['installed'])
        response = Response(self.data)
        response.url = 'http://example.invalid/component.zip'
        with patch.object(optional_runtime, 'urlopen', return_value=response):
            self.runtime.start(True)
            self.runtime.thread.join(5)
        self.assertFalse(self.runtime.target().exists())
        self.assertEqual(list(self.runtime.home.iterdir()), [])

    def test_missing_runtime_does_not_break_base_api(self):
        service = desktop_api.DesktopService(self.home)
        self.addCleanup(service.pool.shutdown)
        with patch.object(optional_runtime, 'urlopen') as download:
            status = service.dispatch('POST', '/components/runtime/status', {}, None)
            self.assertFalse(status['installed'])
            service.dispatch('POST', '/components/runtime/cancel', {}, None)
            self.assertIn('exportConfigured', service.dispatch('POST', '/settings/read', {}, None))
            self.assertEqual(service.dispatch('GET', '/health', {}, None)['status'], 'ok')
            download.assert_not_called()

    def test_frozen_consumers_use_same_verified_command(self):
        self.install()
        with patch.object(optional_runtime.sys, 'frozen', True, create=True), \
             patch.object(optional_runtime, 'RuntimeComponent', return_value=self.runtime):
            ocr = optional_runtime.worker_command(home=self.home)
            semantic = optional_runtime.worker_command(True, self.home)
        self.assertEqual(semantic, ocr + ['--semantic'])

    def test_base_bundle_does_not_include_runtime(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'frontend/vite-app/src-tauri/tauri.conf.json').read_text())
        self.assertFalse(config['bundle']['resources'])
        script = (root / 'scripts/build_windows.ps1').read_text()
        self.assertNotIn("Copy-Item -LiteralPath 'dist/backend/ocr-runtime'", script)
        self.assertNotIn('packaging/ocr.spec', script)

    def test_failure_messages_are_actionable_and_do_not_echo_details(self):
        from urllib.error import URLError
        import errno
        cases = [(URLError('sensitive-secret'), '网络'),
                 (OSError(errno.ENOSPC, 'sensitive-secret'), '磁盘'),
                 (PermissionError('sensitive-secret'), '权限'),
                 (ValueError('sensitive-secret'), '校验')]
        for error, expected in cases:
            with self.subTest(expected=expected), patch.object(optional_runtime, 'urlopen', side_effect=error):
                self.runtime.start(True)
                self.runtime.thread.join(5)
                status = self.runtime.status()
                self.assertEqual(status['state'], 'failed')
                self.assertIn(expected, status['error'])
                self.assertNotIn('sensitive-secret', json.dumps(status))
        self.install()
        self.assertEqual(self.runtime.status()['error'], '')

    def test_ocr_rejects_corrupt_runtime_before_process_launch(self):
        from hope_archive import ocr
        self.install()
        (self.runtime.target() / WORKER).write_bytes(b'corrupt')
        jobs = ocr.OCRJobs(self.home)
        with patch.object(optional_runtime.sys, 'frozen', True, create=True), \
             patch.object(optional_runtime, 'RuntimeComponent', return_value=self.runtime), \
             patch.object(ocr.subprocess, 'Popen') as launch:
            identity = jobs.start([{'name': 'synthetic.png', 'data': 'AA=='}])['jobId']
            import time
            deadline = time.monotonic() + 5
            while jobs.status(identity)['state'] == 'running' and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(jobs.status(identity)['state'], 'failed')
            launch.assert_not_called()
