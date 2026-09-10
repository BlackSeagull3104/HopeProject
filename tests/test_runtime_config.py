"""Offline coverage for distributable configuration; never prints constants."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import auth, desktop_api


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for context in (patch.dict(os.environ, {}, clear=True),
                        patch.object(auth, 'AUTH_ENV_FILE', self.base / '.env'),
                        patch.object(auth, 'AUTH_CONFIG_DESKTOP', False)):
            context.start()
            self.addCleanup(context.stop)

    def test_both_packaged_constants_without_any_file(self):
        auth.configure_desktop()
        with patch.object(Path, 'read_text', side_effect=AssertionError('Desktop must not read .env')):
            for name in ('SEND_CODE_PROTOCOL_KEY', 'LOGIN_PROTOCOL_KEY'):
                self.assertTrue(bool(auth.get_protocol_key(name)))

    def test_development_override_and_explicit_environment(self):
        auth.AUTH_ENV_FILE.write_text('LOGIN_PROTOCOL_KEY=fixture-first\nLOGIN_PROTOCOL_KEY="fixture-last"\n')
        self.assertEqual(auth.get_protocol_key('LOGIN_PROTOCOL_KEY'), 'fixture-last')
        with patch.dict(os.environ, {'LOGIN_PROTOCOL_KEY': 'fixture-env'}):
            self.assertEqual(auth.get_protocol_key('LOGIN_PROTOCOL_KEY'), 'fixture-env')
            auth.configure_desktop()
            self.assertEqual(auth.get_protocol_key('LOGIN_PROTOCOL_KEY'), 'fixture-env')
        with patch.dict(os.environ, {'LOGIN_PROTOCOL_KEY': ''}):
            with self.assertRaisesRegex(auth.AuthError, '配置为空'):
                auth.get_protocol_key('LOGIN_PROTOCOL_KEY')

    def test_desktop_ignores_developer_and_legacy_user_files(self):
        auth.AUTH_ENV_FILE.write_text('LOGIN_PROTOCOL_KEY=fixture-development\n')
        (self.base / 'HopeArchive.env').write_text('LOGIN_PROTOCOL_KEY=fixture-legacy\n')
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.base), 'HOPE_ARCHIVE_HOME': str(self.base / 'profile')}):
            auth.configure_desktop()
            self.assertTrue(auth.get_protocol_key('LOGIN_PROTOCOL_KEY') == auth.APPLICATION_PROTOCOL['LOGIN_PROTOCOL_KEY'])

    def test_missing_packaged_defaults_fail_before_network_without_values(self):
        auth.configure_desktop()
        with patch.object(auth, 'APPLICATION_PROTOCOL', {}), patch.object(auth, '_post_auth') as transport:
            for key, action in (
                ('SEND_CODE_PROTOCOL_KEY', lambda: auth.send_security_code('fixture-mobile')),
                ('LOGIN_PROTOCOL_KEY', lambda: auth.login_by_security_code('fixture-mobile', 'fixture-code'))):
                with self.subTest(key=key), self.assertRaises(auth.AuthError) as caught:
                    action()
                self.assertIn(key, str(caught.exception))
                self.assertNotIn('.env', str(caught.exception))
                self.assertNotIn('fixture-mobile', str(caught.exception))
            transport.assert_not_called()

    def test_defaults_only_supply_application_constants(self):
        self.assertEqual(set(auth.APPLICATION_PROTOCOL), {'SEND_CODE_PROTOCOL_KEY', 'LOGIN_PROTOCOL_KEY'})
        for key in ('password', 'mobile', 'token', 'cookie', 'session', 'Authorization'):
            with self.assertRaises(auth.AuthError):
                auth.get_protocol_key(key)

    def test_protocol_signatures_work_offline_without_config(self):
        auth.configure_desktop()
        self.assertEqual(len(auth.make_send_code_signature('fixture-mobile')), 40)
        self.assertEqual(len(auth.make_login_sign('fixture-mobile', 'fixture-code')), 40)
        self.assertEqual(len(auth.make_password_login_signature('fixture-mobile', 'fixture-password')), 40)

    def test_health_never_returns_constants_or_user_credentials(self):
        service = desktop_api.DesktopService(self.base)
        self.addCleanup(service.pool.shutdown)
        response = service.dispatch('GET', '/health', None, None)
        self.assertEqual(set(response), {'status', 'defaultOutputDir'})
        for value in auth.APPLICATION_PROTOCOL.values():
            self.assertFalse(value in str(response))

    def test_frontend_does_not_contain_constants(self):
        root = Path(__file__).resolve().parents[1] / 'frontend/vite-app/src'
        for path in root.rglob('*'):
            if path.is_file():
                content = path.read_bytes()
                for value in auth.APPLICATION_PROTOCOL.values():
                    self.assertFalse(value.encode() in content, str(path.relative_to(root)))


if __name__ == '__main__':
    unittest.main()
