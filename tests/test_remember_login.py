import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from hope_archive import auth
from hope_archive.desktop_api import DesktopService
from hope_archive.local_api import RequestError
from hope_archive.secure_store import SecretStoreError

class Store:
    value = None
    def read(self, name): return self.value
    def write(self, name, value): self.value = value
    def delete(self, name): self.value = None

class RememberLoginTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(); self.service = self.fresh()
    def fresh(self):
        service = DesktopService(Path(self.temp.name)); service.login_store = self.store
        self.addCleanup(service.pool.shutdown); return service
    def login(self, remember=True, user='fixture-account'):
        with patch.object(auth,'login_by_password',return_value=auth.AuthResult(user,mobile='never-persist',nickname='Synthetic')):
            return self.service.dispatch('POST','/auth/login/password',{'mobile':'fixture-mobile','secret':'fixture-password','remember':remember},None)
    def test_restart_fixed_expiry_new_token_no_sensitive_files(self):
        with patch('hope_archive.desktop_api.time.time',return_value=1000): original=self.login()
        saved=self.store.value
        with patch('hope_archive.desktop_api.time.time',return_value=1100):
            service=self.fresh();restored=service.restore_login()['session']
            self.assertEqual(restored['userId'],original['userId'])
            self.assertNotEqual(restored['token'],original['token'])
            self.assertEqual(service.restore_login()['session'],restored)
        self.assertEqual(self.store.value,saved)
        for secret in ('fixture-mobile','fixture-password','never-persist',original['token']):self.assertNotIn(secret,saved)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    def test_expiry_and_clock_rollback(self):
        for clock in (999,44200,50000):
            with patch('hope_archive.desktop_api.time.time',return_value=1000):self.login()
            with patch('hope_archive.desktop_api.time.time',return_value=clock):self.assertIsNone(self.fresh().restore_login()['session'])
            self.assertIsNone(self.store.value)
    def test_switch_without_remember_clears_old_account(self):
        first=self.login();second=self.login(False,'second-fixture')
        self.assertIsNone(self.store.value)
        with self.assertRaises(RequestError):self.service.session(first['token'])
        self.assertEqual(self.service.session(second['token'])['userId'],'second-fixture')
        self.assertIsNone(self.fresh().restore_login()['session'])
    def test_expired_logout_still_clears(self):
        first=self.login();self.service.sessions[first['token']]['expires']=0
        self.service.dispatch('POST','/auth/logout',{},first['token'])
        self.assertFalse(self.service.sessions);self.assertIsNone(self.fresh().restore_login()['session'])
    def test_malformed_and_extra_fields_rejected(self):
        for raw in ('bad','null','[]','{"version":1}'):
            self.store.value=raw;self.assertIsNone(self.fresh().restore_login()['session'])
        self.login();value=json.loads(self.store.value);value['identity']['mobile']='forbidden';self.store.value=json.dumps(value)
        self.assertIsNone(self.fresh().restore_login()['session'])
    def test_storage_failures_are_visible_and_do_not_echo(self):
        with patch.object(self.store,'write',side_effect=SecretStoreError('secret-detail')):
            with self.assertRaises(RequestError) as failure:self.login()
        self.assertNotIn('secret-detail',str(failure.exception));self.assertFalse(self.service.sessions)
        self.login()
        with patch.object(self.store,'delete',side_effect=SecretStoreError('secret-detail')):
            with self.assertRaises(RequestError):self.service.dispatch('POST','/auth/logout',{},None)
    def test_restore_does_not_call_login_or_sms(self):
        self.login()
        with patch.object(auth,'_post_auth',side_effect=AssertionError('Network forbidden')):
            self.assertIsNotNone(self.fresh().restore_login()['session'])
    def test_capability_boolean_only(self):
        self.login();value=json.loads(self.store.value);value['identity']['specialExperience']=True;self.store.value=json.dumps(value)
        restored=self.fresh().restore_login()['session']
        self.assertTrue(restored['specialExperience'])
        self.assertEqual(set(restored),{'token','userId','displayName','specialExperience'})
