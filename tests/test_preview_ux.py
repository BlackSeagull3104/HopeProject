from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import auth, api, preview, application, local_api
from hope_archive.export_documents import export_range, range_filename, ExportFormat
from hope_archive.export_markdown import render_diary


def entry(identifier=1):
    return {'dairyId': identifier, 'noteDate': '2024-01-02', 'noteType': 2,
            'dairy': '合成测试正文', 'user': {'id': 'fixture-owner'},
            'weatherIdentity': 'weather_qing', 'emotionIdentity': 'emotion_ha',
            'noteInfo2': {'richTextInfo': [{'type': 2, 'fileList': [{'mediaUrl': 'https://example.invalid/image.png'}]}]},
            'commentList': [{'detail': [{'comments': '合成留言', 'fromName': '合成作者'}]}]}


class PreviewUXTests(unittest.TestCase):
    def test_auth_semantic_allowlist_and_unknown(self):
        cases = [('手机号未注册', 'code', 'AUTH_PHONE_NOT_REGISTERED', '该手机号尚未注册 Hope'),
                 ('验证码错误', 'code', 'AUTH_CODE_INVALID', '验证码错误，请重新输入'),
                 ('密码错误', 'password', 'AUTH_PASSWORD_INVALID', '密码错误，请重新输入')]
        for text, action, expected, message in cases:
            self.assertEqual(auth.public_auth_error(auth.AuthError('generic', server_message=text), action), (expected, message))
        for text in ('unknown fixture-private', '账号或密码错误', '密码错误 fixture-secret'):
            code, message = auth.public_auth_error(auth.AuthError('fixture-secret', server_message=text), 'password')
            self.assertEqual(code, 'AUTH_UNKNOWN_ERROR')
            self.assertNotIn('fixture-secret', message)
        self.assertEqual(auth.public_auth_error(auth.AuthError('x', server_message='验证码错误'), 'password')[0], 'AUTH_UNKNOWN_ERROR')

    def test_network_auth_and_local_error_code(self):
        with patch.object(auth, 'build_opener') as opener:
            opener.return_value.open.side_effect = URLError('fixture-private')
            with self.assertRaises(auth.AuthError) as caught:
                auth._post_auth(auth.PASSWORD_LOGIN_ENDPOINT, {})
            self.assertEqual(caught.exception.code, 'AUTH_NETWORK_ERROR')
            self.assertNotIn('fixture-private', str(caught.exception))
        service = local_api.LocalService()
        self.addCleanup(service.pool.shutdown)
        with patch.object(auth, 'login_by_password', side_effect=auth.AuthError('fixture-secret', server_message='密码错误')):
            with self.assertRaises(local_api.RequestError) as caught:
                service.authenticate('password', {'mobile': 'fixture-mobile', 'secret': 'fixture-secret'})
            self.assertEqual(caught.exception.code, 'AUTH_PASSWORD_INVALID')
            self.assertNotIn('fixture-secret', str(caught.exception))

    def test_preview_request_no_writes_and_multiple_pages(self):
        responses = [dict(status=1, datas=dict(total=2, list=[entry(1)])), dict(status=1, datas=dict(total=2, list=[entry(2)]))]
        with patch.object(api, 'urlopen', side_effect=[BytesIO(json.dumps(v).encode()) for v in responses]) as network, patch.object(api, 'save_raw_response') as raw, patch.object(api, 'save_diaries') as save:
            result = preview.for_date('fixture-owner', '2024-01-02', 'discovery_diary')
        raw.assert_not_called(); save.assert_not_called()
        self.assertEqual(len(result['diaries']), 2)
        for i, call in enumerate(network.call_args_list):
            body = json.loads(call.args[0].data)
            self.assertEqual((body['beginDate'], body['endDate']), ('2024-01-02', '2024-01-02'))
            self.assertEqual((body['userId'], body['noteType'], body['pageNum']), ('fixture-owner', 2, i+1))
        self.assertEqual(result['diaries'][0]['comments'][0]['items'][0]['text'], '合成留言')
        self.assertEqual(result['diaries'][0]['content'][0]['kind'], 'image')

    def test_empty_unknown_network_future_and_scope(self):
        with patch.object(api, 'fetch_all_diaries', return_value=[]):
            self.assertEqual(preview.for_date('fixture-owner', '2024-01-02')['diaries'], [])
        item = entry(); item['noteType'] = 99
        with patch.object(api, 'fetch_all_diaries', return_value=[item]):
            self.assertEqual(preview.for_date('fixture-owner', '2024-01-02')['diaries'][0]['diary_type'], 'unknown')
            with self.assertRaises(preview.PreviewError): preview.for_date('another-owner', '2024-01-02')
        with patch.object(api, 'fetch_all_diaries', side_effect=api.DiaryAPIError('fixture-secret')):
            with self.assertRaises(preview.PreviewError) as caught: preview.for_date('fixture-owner', '2024-01-02')
            self.assertNotIn('fixture-secret', str(caught.exception))
        with patch.object(api, 'fetch_all_diaries') as fetch:
            with self.assertRaises(application.ArchiveError): preview.for_date('fixture-owner', (date.today()+timedelta(days=1)).isoformat())
            fetch.assert_not_called()

    def test_local_session_media_scope_and_no_remote_urls(self):
        service = local_api.LocalService(); self.addCleanup(service.pool.shutdown)
        service.sessions['fixture-session'] = {'userId': 'fixture-owner', 'expires': time.monotonic()+60}
        with patch.object(api, 'fetch_all_diaries', return_value=[entry()]):
            result = service.dispatch('POST', '/diaries/preview', {'date': '2024-01-02'}, 'fixture-session')
        self.assertNotIn('https://', json.dumps(result))
        key = result['diaries'][0]['content'][0]['media'][0]['key']
        with patch.object(preview, 'load_media', return_value={'source': 'data:image/png;base64,fixture'}) as load:
            service.dispatch('POST', '/diaries/preview/media', {'key': key}, 'fixture-session')
            load.assert_called_once_with('https://example.invalid/image.png')
        with self.assertRaises(local_api.RequestError): service.dispatch('POST', '/diaries/preview', {'date': '2024-01-02', 'userId': 'other'}, 'fixture-session')
        with self.assertRaises(local_api.RequestError): service.dispatch('POST', '/diaries/preview', {'date': '2024-01-02'}, '')

    def test_range_names_and_all_formats(self):
        for format in ExportFormat:
            ext = 'md' if format == ExportFormat.MARKDOWN else format.value
            self.assertEqual(range_filename('小明', '2024-01-01', '2024-01-02', format), f'小明的日记_2024-01-01--2024-01-02.{ext}')
            self.assertTrue(range_filename(None, '2024-01-01', '2024-01-02', format).startswith('Hope日记_'))
            name = range_filename('a/b:c*?"<>|. ', '2024-01-01', '2024-01-02', format)
            self.assertFalse(any(c in name for c in '\\/:*?"<>|'))
            with tempfile.TemporaryDirectory() as root:
                document = {'diaries': [{'note_date': '2024-01-01', 'original_text': '合成正文一'}, {'note_date': '2024-01-02', 'original_text': '合成正文二'}]}
                stats = export_range(document, {}, root, root, format, '小明', '2024-01-01', '2024-01-02')
                self.assertEqual(stats['generated'], 1)
                path = Path(root) / range_filename('小明', '2024-01-01', '2024-01-02', format)
                self.assertTrue(path.is_file())
                self.assertEqual(export_range(document, {}, root, root, format, '小明', '2024-01-01', '2024-01-02')['skipped'], 1)

    def test_markdown_side_by_side_and_known_emoji(self):
        text = render_diary({'note_date': '2024-01-02', 'emotion': {'identity': 'emotion_ha'}, 'weather': {'identity': 'weather_qing'}}, {}, Path('.'), Path('fixture.md'))
        self.assertIn('心情：哈　　天气：晴 ☀️', text)

    def test_media_rejects_private_hosts_and_oversize(self):
        import socket
        with patch('socket.getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]), patch('urllib.request.build_opener') as opener:
            with self.assertRaises(preview.PreviewError): preview.load_media('https://fixture.invalid/media')
            opener.assert_not_called()
        from email.message import Message
        response = BytesIO(b'x' * (8 * 1024 * 1024 + 1))
        response.headers = Message(); response.headers['Content-Type'] = 'image/png'
        with patch('socket.getaddrinfo', return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]), patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            with self.assertRaises(preview.PreviewError): preview.load_media('https://fixture.invalid/media')

    def test_failed_response_is_not_empty(self):
        with patch.object(api, 'urlopen', return_value=BytesIO(b'{"status":0,"datas":{"total":0,"list":[]}}')):
            with self.assertRaises(preview.PreviewError): preview.for_date('fixture-owner', '2024-01-02')
