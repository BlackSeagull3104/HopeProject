"""Desktop adapter contracts; no real credentials or network calls to Hope."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import desktop_api, local_api


class DesktopTests(unittest.TestCase):
    def test_absolute_profile_override_and_default(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'HOPE_ARCHIVE_HOME': folder}):
                self.assertEqual(desktop_api.user_home(), Path(folder))
            with patch.dict(os.environ, {'HOPE_ARCHIVE_HOME': 'relative'}):
                with self.assertRaises(ValueError):
                    desktop_api.user_home()
            with patch.dict(os.environ, {'HOPE_ARCHIVE_HOME': '', 'LOCALAPPDATA': folder}):
                self.assertEqual(desktop_api.user_home(), Path(folder) / 'HopeArchive')

    def test_desktop_health_and_original_session_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            service = desktop_api.DesktopService(Path(folder))
            self.addCleanup(service.pool.shutdown)
            self.assertEqual(service.dispatch('GET', '/health', None, None),
                {'status': 'ok', 'defaultOutputDir': str(Path(folder) / 'archives')})
            with self.assertRaises(local_api.RequestError) as caught:
                service.dispatch('POST', '/archive/download', {}, None)
            self.assertEqual(caught.exception.status, 401)

    def test_existing_development_health_is_unchanged(self):
        service = local_api.LocalService()
        self.addCleanup(service.pool.shutdown)
        self.assertEqual(service.dispatch('GET', '/health', None, None)['defaultOutputDir'],
                         str(local_api.PROJECT / 'data'))


if __name__ == '__main__':
    unittest.main()
