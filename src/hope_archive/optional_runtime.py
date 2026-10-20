"""One explicitly installed, integrity-checked runtime shared by OCR and Hybrid."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
from urllib.request import Request, urlopen
import zipfile
import uuid

from .runtime_catalog import RUNTIME
from .settings import profile_dir

WORKER = 'hope-archive-ocr.exe'


def safe_name(name):
    parts = PurePosixPath(name).parts
    return (bool(parts) and not name.startswith('/') and '\\' not in name
            and ':' not in name and all(p not in ('..', '.') for p in parts)
            and all(not p.endswith((' ', '.')) for p in parts)
            and all(not re.fullmatch(r'(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])', p.split('.')[0]) for p in parts))


class RuntimeComponent:
    def __init__(self, home=None, catalog=RUNTIME):
        self.home = (Path(home) if home is not None else profile_dir()) / 'components' / 'inference'
        self.catalog = catalog
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.state = ''
        self.received = 0
        self.thread = None
        self.verified_stamp = None

    def target(self):
        c = self.catalog
        if not c or not re.fullmatch(r'[a-zA-Z0-9_-]+', c['version']):
            raise ValueError('此版本尚未提供可下载的本地组件。')
        return self.home / c['version']

    def verify(self, directory):
        expected = self.catalog['files']
        if WORKER not in expected or directory.is_symlink():
            raise ValueError('组件校验失败。')
        actual = set()
        for path in directory.rglob('*'):
            if path.is_symlink(): raise ValueError('组件路径无效。')
            if path.is_file(): actual.add(path.relative_to(directory).as_posix())
        if actual != set(expected): raise ValueError('组件文件不完整。')
        for name, meta in expected.items():
            if not safe_name(name): raise ValueError('组件路径无效。')
            path = directory / name
            if path.stat().st_size != meta['bytes']: raise ValueError('组件大小不符。')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != meta['sha256']:
                    raise ValueError('组件校验失败。')

    def status(self):
        with self.lock:
            ready = False
            if self.catalog and (self.target() / WORKER).is_file():
                try:
                    directory = self.target()
                    stamp = tuple(sorted((str(p.relative_to(directory)), p.stat().st_size, p.stat().st_mtime_ns)
                                         for p in directory.rglob('*') if p.is_file()))
                    if stamp != self.verified_stamp:
                        self.verify(directory)
                        self.verified_stamp = stamp
                    ready = True
                except (OSError, ValueError):
                    if not self.thread or not self.thread.is_alive(): self.state = 'failed'
            return {'state': self.state or ('installed' if ready else 'not_installed'),
                    'installed': ready, 'available': self.catalog is not None,
                    'downloadBytes': self.catalog['bytes'] if self.catalog else None,
                    'diskBytes': sum(f['bytes'] for f in self.catalog['files'].values()) if self.catalog else None,
                    'receivedBytes': self.received}

    def command(self):
        directory = self.target()
        try: self.verify(directory)
        except (OSError, ValueError):
            raise ValueError('请先安装或修复本地识别组件。') from None
        return [str(directory / WORKER)]

    def start(self, confirmed):
        if confirmed is not True: raise ValueError('请先确认下载组件。')
        with self.lock:
            if self.thread and self.thread.is_alive(): return self.status()
            self.target()
            if self.status()['installed']:
                self.command()
                self.state = ''
                return self.status()
            if self.target().exists():
                # Keep damaged payload for recovery; never overwrite a generation.
                self.target().rename(self.home / ('damaged-' + uuid.uuid4().hex))
            self.stop.clear()
            self.state, self.received = 'downloading', 0
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            return self.status()

    def cancel(self):
        with self.lock:
            self.stop.set()
            if self.thread and self.thread.is_alive(): self.state = 'cancelling'
            return self.status()

    def close(self):
        self.cancel()
        if self.thread: self.thread.join(timeout=35)

    def run(self):
        staging = None
        try:
            c = self.catalog
            if not c['url'].startswith('https://'): raise ValueError('HTTPS required')
            self.home.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.home).free < c['bytes'] + sum(f['bytes'] for f in c['files'].values()) + 16*1024*1024:
                raise ValueError('Insufficient disk')
            staging = Path(tempfile.mkdtemp(prefix='download-', dir=self.home))
            archive = staging / 'component.zip'
            deadline = time.monotonic() + 900
            digest = hashlib.sha256()
            with urlopen(Request(c['url'], headers={'Accept-Encoding': 'identity'}), timeout=30) as response, archive.open('xb') as stream:
                if not response.url.startswith('https://'): raise ValueError('Invalid redirect')
                while block := response.read(1024*1024):
                    if self.stop.is_set() or time.monotonic() > deadline: raise InterruptedError()
                    self.received += len(block)
                    if self.received > c['bytes']: raise ValueError('Oversized download')
                    digest.update(block)
                    stream.write(block)
            if self.received != c['bytes'] or digest.hexdigest() != c['sha256']:
                raise ValueError('Invalid download')
            self.state = 'verifying'
            payload = staging / 'payload'
            payload.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                seen = set()
                for item in bundle.infolist():
                    name = item.filename
                    if item.is_dir(): continue
                    if (not safe_name(name) or name.casefold() in seen or name not in c['files']
                            or stat.S_ISLNK(item.external_attr >> 16)
                            or item.file_size != c['files'][name]['bytes']):
                        raise ValueError('Invalid archive')
                    seen.add(name.casefold())
                    target = payload / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(item) as source, target.open('xb') as output:
                        while block := source.read(1024*1024):
                            if self.stop.is_set(): raise InterruptedError()
                            output.write(block)
            self.verify(payload)
            with self.lock:
                if self.stop.is_set(): raise InterruptedError()
                # An immutable generation is shared by both consumers.
                payload.rename(self.target())
                self.verified_stamp = None
                self.state = ''
        except Exception:
            with self.lock:
                self.state = 'cancelled' if self.stop.is_set() else 'failed'
        finally:
            if staging is not None: shutil.rmtree(staging, ignore_errors=True)


def worker_command(semantic=False, home=None):
    if getattr(sys, 'frozen', False):
        return RuntimeComponent(home).command() + (['--semantic'] if semantic else [])
    # Developers explicitly manage dependencies in their environment; production
    # never falls back to the bundled legacy worker or to an unverified binary.
    return [getattr(sys, '_base_executable', sys.executable), '-B', '-X', 'utf8',
            '-m', 'hope_archive.semantic_worker' if semantic else 'hope_archive.ocr_worker']
