"""Offline auth tests use synthetic fields; no live SMS or login requests."""
from dataclasses import asdict
from copy import deepcopy
from pathlib import Path
import io
import json
from contextlib import redirect_stdout
from urllib.parse import parse_qs
from urllib.error import HTTPError, URLError
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import auth, application


class AuthTests(unittest.TestCase):
    def setUp(self):
        config = patch.dict(auth.os.environ, {'SEND_CODE_PROTOCOL_KEY':'fixture-send-key', 'LOGIN_PROTOCOL_KEY':'fixture-login-key'})
        config.start()
        self.addCleanup(config.stop)

    def test_local_config_loading_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('# fixture config\nSEND_CODE_PROTOCOL_KEY="local-fixture"\n', encoding='utf-8')
            with patch.object(auth, 'AUTH_ENV_FILE', path), patch.dict(auth.os.environ, {}, clear=True):
                self.assertEqual(auth.get_protocol_key('SEND_CODE_PROTOCOL_KEY'), 'local-fixture')
                with patch.dict(auth.os.environ, {'SEND_CODE_PROTOCOL_KEY':'env-fixture'}):
                    self.assertEqual(auth.get_protocol_key('SEND_CODE_PROTOCOL_KEY'), 'env-fixture')

    def test_missing_config_prevents_request(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(auth,'AUTH_ENV_FILE',Path(folder)/'absent'), patch.dict(auth.os.environ,{},clear=True), patch.object(auth, 'APPLICATION_PROTOCOL', {}), patch.object(auth,'_post_auth') as transport:
                with self.assertRaisesRegex(auth.AuthError,'SEND_CODE_PROTOCOL_KEY'):
                    auth.send_security_code('fixture-mobile')
                with self.assertRaisesRegex(auth.AuthError,'LOGIN_PROTOCOL_KEY'):
                    auth.login_by_password('fixture-mobile','fixture-password')
                transport.assert_not_called()

    def test_empty_environment_config_is_not_silently_replaced(self):
        with patch.dict(auth.os.environ, {'LOGIN_PROTOCOL_KEY':''}):
            with self.assertRaisesRegex(auth.AuthError,'配置为空'):
                auth.make_login_sign('fixture-mobile','fixture-code')

    def test_confirmed_endpoints(self):
        self.assertEqual(auth.SEND_SECURITY_CODE_ENDPOINT, 'https://hope.wantexe.com/services/checkCodeService/sendCheckCodeV2')
        self.assertEqual(auth.LOGIN_BY_SECURITY_CODE_ENDPOINT, 'https://hope.wantexe.com/services/v2/user/loginBySecurityCode')
        self.assertEqual(auth.ONE_CLICK_LOGIN_ENDPOINT, 'https://hope.wantexe.com/services/v2/user/loginEasily')

    def test_payload_fields_preserve_supplied_values(self):
        self.assertEqual(auth.build_send_security_code_payload('fixture-mobile', 'fixture-signature'),
            {'mobile':'fixture-mobile', 'codeType':3, 'signature':'fixture-signature'})
        self.assertEqual(auth.build_login_by_security_code_payload('fixture-mobile', 'fixture-code', ' opaque-fixture '),
            {'wxOpenId':'', 'mobile':'fixture-mobile', 'securityCode':'fixture-code', 'sign':' opaque-fixture '})

    def test_confirmed_signature_vectors_and_automatic_generation(self):
        self.assertEqual(auth.make_send_code_signature('fixture-mobile'), '4f30a0e88da52b18a76669fc3462d8d9e589cf0e')
        self.assertEqual(auth.make_login_sign('fixture-mobile', 'fixture-code'), '34a5dfb51e68438cab4bc5947f9327359202bbf2')
        self.assertEqual(auth.make_password_login_signature('fixture-mobile', 'fixture-password'), 'f95bb9c238e87a2ce77fdb4cf731d390dcfffe00')
        self.assertEqual(auth.build_send_security_code_payload('fixture-mobile')['signature'], auth.make_send_code_signature('fixture-mobile'))
        self.assertEqual(auth.build_login_by_security_code_payload('fixture-mobile','fixture-code')['sign'], auth.make_login_sign('fixture-mobile','fixture-code'))

    def test_empty_fields_rejected_without_echoing_values(self):
        for value in (None, '', ' ', 123):
            with self.subTest(value=value):
                with self.assertRaises(auth.AuthError):
                    auth.build_login_by_security_code_payload(value, 'fixture-code', 'fixture-sign')
        with self.assertRaises(auth.AuthError):
            auth.build_send_security_code_payload('fixture-mobile', '')
        with self.assertRaises(auth.AuthError):
            auth.build_login_by_security_code_payload('fixture-mobile', '', 'fixture-sign')

    def test_success_allowlist_and_input_unchanged(self):
        response={'status':1, 'msg':'', 'datas':{'id':42, 'mobile':'fixture-mobile',
            'wxOpenId':'fixture-openid', 'deviceToken':'fixture-device', 'yunXinToken':'fixture-token'}}
        before=deepcopy(response)
        with patch('builtins.open', side_effect=AssertionError('No auth persistence')), \
             patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            result=auth.parse_login_response(response)
        self.assertEqual(asdict(result), {'user_id':'42', 'mobile':'fixture-mobile', 'nickname':None})
        self.assertEqual(response,before)
        self.assertNotIn('42',repr(result))

    def test_unconfirmed_status_is_generic_and_server_message_not_echoed(self):
        for status in (None, 0, 2, '1', True):
            with self.subTest(status=status):
                with self.assertRaises(auth.AuthError) as caught:
                    auth.parse_login_response({'status':status, 'msg':'fixture server message', 'datas':{'id':42}})
                self.assertEqual(caught.exception.server_message,'fixture server message')
                self.assertNotIn('fixture server message',str(caught.exception))
                self.assertNotIn('fixture server message',repr(caught.exception))

    def test_missing_or_malformed_identity(self):
        for response in (None, [], {'status':1}, {'status':1,'datas':[]},
                         *({'status':1,'datas':{'id':value}} for value in (None, '', ' ', False, {}, 0, -1))):
            with self.subTest(response=response):
                with self.assertRaises(auth.AuthError): auth.parse_login_response(response)

    def test_form_transport_and_confirmed_sms_success(self):
        with patch.object(auth, 'build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"status": 1, "msg": "fixture"}')
            response = auth.send_security_code('fixture-mobile', 'fixture+&signature', timeout=9)
        self.assertEqual(response['status'], 1)
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, auth.SEND_SECURITY_CODE_ENDPOINT)
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Content-type'), 'application/x-www-form-urlencoded')
        self.assertEqual(parse_qs(request.data.decode()), {'mobile':['fixture-mobile'], 'codeType':['3'], 'signature':['fixture+&signature']})
        self.assertEqual(opener.return_value.open.call_args.kwargs['timeout'], 9)
        self.assertIsInstance(opener.call_args.args[0], auth._NoAuthRedirect)

    def test_json_login_transport(self):
        with patch.object(auth, 'build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"status":1,"datas":{"id":42,"deviceToken":"fixture"}}')
            result = auth.login_by_security_code('fixture-mobile', 'fixture-code', 'fixture-sign')
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, auth.LOGIN_BY_SECURITY_CODE_ENDPOINT)
        self.assertEqual(request.get_header('Content-type'), 'application/json')
        self.assertEqual(json.loads(request.data), auth.build_login_by_security_code_payload('fixture-mobile', 'fixture-code', 'fixture-sign'))
        self.assertEqual(asdict(result), {'user_id':'42', 'mobile':None, 'nickname':None})

    def test_transport_errors_are_generic_and_not_retried(self):
        for error in (URLError('fixture-private'), TimeoutError('fixture-private'),
                      HTTPError('https://fixture.invalid', 403, 'fixture-private', {}, io.BytesIO(b'fixture-private'))):
            with patch.object(auth, 'build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(auth.AuthError) as caught:
                    auth.send_security_code('fixture-mobile', 'fixture-signature')
                self.assertNotIn('fixture-private', str(caught.exception))
                opener.return_value.open.assert_called_once()
        for body in (b'not-json', b'[]'):
            with patch.object(auth, 'build_opener') as opener:
                opener.return_value.open.return_value = io.BytesIO(body)
                with self.assertRaises(auth.AuthError):
                    auth.send_security_code('fixture-mobile', 'fixture-signature')

    def test_invalid_timeout_prevents_network(self):
        with patch.object(auth, 'build_opener') as opener:
            for timeout in (0, -1, float('inf'), float('nan')):
                with self.assertRaises(auth.AuthError):
                    auth.send_security_code('fixture-mobile', 'fixture-signature', timeout=timeout)
            opener.assert_not_called()

    def test_password_wire_and_sms_failure(self):
        with patch.object(auth, 'build_opener') as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"status":1,"datas":{"id":42,"nickName":"fixture"}}')
            result = auth.login_by_password('fixture-mobile', 'fixture-password')
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://hope.wantexe.com/services/userService/login')
        self.assertEqual(request.get_header('Content-type'), 'application/x-www-form-urlencoded')
        self.assertEqual(parse_qs(request.data.decode(),keep_blank_values=True),
            {'mobile':['fixture-mobile'],'wxOpenId':[''],'password':['fixture-password'],
             'signature':['f95bb9c238e87a2ce77fdb4cf731d390dcfffe00']})
        self.assertEqual(result.nickname, 'fixture')
        with patch.object(auth, '_post_auth', return_value={'status':2,'message':'fixture failure'}):
            with self.assertRaises(auth.AuthError) as caught:
                auth.send_security_code('fixture-mobile')
        self.assertEqual(caught.exception.server_message, 'fixture failure')

    def test_result_supplies_existing_application_user_id(self):
        result=auth.parse_login_response({'status':1,'datas':{'id':'fixture-id'}})
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(application, 'fetch_all_diaries', return_value=[]) as fetch, \
                 patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
                archive = application.export_archive(
                    result.user_id, '2024-01-01', '2024-01-02', 0, Path(temporary))
            self.assertEqual(fetch.call_args.args[0], 'fixture-id')
            self.assertTrue(archive.complete)
            self.assertTrue((archive.output_dir / 'processed/diaries.normalized.json').is_file())



if __name__ == '__main__':
    unittest.main()
