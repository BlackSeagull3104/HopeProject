"""Real loopback HTTP and real archive pipeline; only Hope transport is mocked."""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import auth, local_api


class LocalAPITests(unittest.TestCase):
    def setUp(self):
        self.server = local_api.make_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.addCleanup(self.close)
        self.token = None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.server.service.pool.shutdown(wait=True)
        self.thread.join()

    def call(self, path, body=None, headers=None):
        values = {'Content-Type': 'application/json', 'X-Hope-Client': 'react', 'Origin': 'http://localhost:5173'}
        if self.token:
            values['Authorization'] = 'Bearer ' + self.token
        values.update(headers or {})
        request = Request(f'http://127.0.0.1:{self.server.server_port}' + path,
            data=json.dumps(body).encode() if body is not None else None, headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                return response.status, json.load(response)
        except HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def login(self, mode='code'):
        with patch.dict(auth.os.environ, {'LOGIN_PROTOCOL_KEY': 'fixture-key'}), \
             patch.object(auth, '_post_auth', return_value={'status': 1, 'datas': {'id': 42, 'deviceToken': 'never-return'}}):
            status, result = self.call('/auth/login/' + mode, {'mobile': 'fixture-mobile', 'secret': 'fixture-secret'})
        self.assertEqual(status, 200)
        self.assertEqual(result['userId'], '42')
        self.assertNotIn('never-return', json.dumps(result))
        self.token = result['token']

    def wait_job(self, job_id):
        for _ in range(100):
            status, job = self.call('/jobs/' + job_id)
            self.assertEqual(status, 200)
            if job['state'] != 'running':
                return job
            time.sleep(.01)
        self.fail('job did not complete')

    def test_login_download_and_offline_export(self):
        self.login()
        body = {'datas': {'total': 1, 'list': [{'dairyId': 7, 'noteDate': '2024-01-01', 'dairy': 'synthetic diary', 'user': {'id': 42}}]}}
        with patch('hope_archive.api.urlopen', return_value=io.BytesIO(json.dumps(body).encode())) as transport:
            status, result = self.call('/archive/download', {'beginDate': '2024-01-01', 'endDate': '2024-01-02', 'outputDir': self.root.name})
            self.assertEqual(status, 200)
            job = self.wait_job(result['jobId'])
            self.assertEqual(json.loads(transport.call_args.args[0].data)['userId'], '42')
        self.assertEqual(job['state'], 'completed')
        run = Path(job['result']['outputDir'])
        self.assertTrue((run / 'archive/2024/01/2024-01-01_7.md').exists())
        output = Path(self.root.name) / 'reading'
        with patch('hope_archive.api.urlopen', side_effect=AssertionError('offline')):
            status, result = self.call('/export/markdown', {'inputPath': str(run / 'processed/diaries.normalized.json'), 'archiveDir': str(run / 'archive'), 'outputDir': str(output)})
            self.assertEqual(status, 200)
            self.assertEqual(self.wait_job(result['jobId'])['state'], 'completed')
        self.assertIn('synthetic diary', (output / '2024/01/2024-01-01_7.md').read_text())

    def test_password_logout_and_expiry(self):
        self.login('password')
        self.assertEqual(self.call('/auth/logout', {})[0], 200)
        self.assertEqual(self.call('/jobs/missing')[0], 401)
        self.login()
        self.server.service.sessions[self.token]['expires'] = 0
        self.assertEqual(self.call('/jobs/missing')[0], 401)

    def test_host_origin_and_json_boundary(self):
        self.assertEqual(self.call('/health')[0], 200)
        self.assertEqual(self.call('/health', headers={'Host': 'evil.test'})[0], 403)
        self.assertEqual(self.call('/auth/send-code', {'mobile': 'fixture'}, {'Origin': 'https://evil.test'})[0], 403)
        self.assertEqual(self.call('/auth/send-code', {'mobile': 'fixture'}, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.call('/archive/download', {})[0], 401)

    def test_send_code_cooldown_and_redaction(self):
        with patch.object(auth, 'send_security_code', return_value={'status': 1}) as send:
            self.assertEqual(self.call('/auth/send-code', {'mobile': 'fixture'})[0], 200)
            self.assertEqual(self.call('/auth/send-code', {'mobile': 'fixture'})[0], 429)
            send.assert_called_once()
        with patch.object(auth, 'login_by_password', side_effect=auth.AuthError('登录失败', server_message='fixture-secret')):
            status, result = self.call('/auth/login/password', {'mobile': 'fixture', 'secret': 'fixture-secret'})
        self.assertEqual(status, 400)
        self.assertNotIn('fixture-secret', json.dumps(result))

    def test_invalid_parameters_and_job_isolation(self):
        self.login()
        request = {'beginDate': '2024-02-02', 'endDate': '2024-02-01', 'outputDir': self.root.name}
        self.assertEqual(self.call('/archive/download', request)[0], 400)
        request.update(beginDate='2024-01-01', userId='another-user')
        self.assertEqual(self.call('/archive/download', request)[0], 400)
        self.server.service.jobs['fixture'] = {'owner': 'someone-else', 'state': 'completed'}
        self.assertEqual(self.call('/jobs/fixture')[0], 404)

    def test_background_failure_and_duplicate_guard(self):
        self.login()
        gate = threading.Event()
        def blocked(*args, **kwargs):
            gate.wait(3)
            raise local_api.application.ArchiveError('获取日记失败')
        body = {'beginDate': '2024-01-01', 'endDate': '2024-01-02', 'outputDir': self.root.name}
        with patch.object(local_api.application, 'export_archive', side_effect=blocked):
            _, result = self.call('/archive/download', body)
            try:
                self.assertEqual(self.call('/archive/download', body)[0], 409)
            finally:
                gate.set()
            self.assertEqual(self.wait_job(result['jobId'])['state'], 'failed')

    def test_export_invalid_file_and_wrong_owner(self):
        self.login()
        body = {'inputPath': str(Path(self.root.name) / 'missing'), 'archiveDir': self.root.name}
        _, result = self.call('/export/markdown', body)
        self.assertEqual(self.wait_job(result['jobId'])['state'], 'failed')
        path = Path(self.root.name) / 'fixture.json'
        path.write_text(json.dumps({'diaries': [{'id': 1, 'author': {'id': 99}}]}))
        body['inputPath'] = str(path)
        _, result = self.call('/export/markdown', body)
        self.assertEqual(self.wait_job(result['jobId'])['state'], 'failed')

    def test_nickname_from_both_login_methods_and_missing_fallback(self):
        for mode in ('code', 'password'):
            for nickname in ('合成昵称', None):
                user = auth.AuthResult('42', nickname=nickname)
                method = 'login_by_security_code' if mode == 'code' else 'login_by_password'
                with patch.object(auth, method, return_value=user):
                    status, result = self.call('/auth/login/' + mode, {'mobile': 'fixture-mobile', 'secret': 'fixture-secret'})
                self.assertEqual(status, 200)
                self.assertEqual(result['displayName'], nickname or 'Hope 用户')
                self.assertEqual(self.server.service.sessions[result['token']]['displayName'], result['displayName'])
                self.assertNotIn('fixture-mobile', json.dumps(result))

    def test_export_formats_filter_and_validation(self):
        self.login()
        path = Path(self.root.name) / 'fixture.json'
        path.write_text(json.dumps({'diaries': [
            {'id': 1, 'note_date': '2024-01-01', 'original_text': 'synthetic selected'},
            {'id': 2, 'note_date': '2024-01-02', 'original_text': 'synthetic excluded'}]}))
        body = {'inputPath': str(path), 'archiveDir': self.root.name, 'beginDate': '2024-01-01', 'endDate': '2024-01-01'}
        for format in ('markdown', 'tex', 'pdf', 'docx'):
            body.update(format=format, outputDir=str(Path(self.root.name) / format))
            status, response = self.call('/export/document', body)
            self.assertEqual(status, 200)
            job = self.wait_job(response['jobId'])
            self.assertEqual(job['state'], 'completed')
            self.assertEqual(job['result']['diaryCount'], 1)
            self.assertEqual(job['result']['format'], format)
        body['format'] = 'invalid'
        self.assertEqual(self.call('/export/document', body)[0], 400)
        body.update(format='markdown', endDate='9999-01-01')
        self.assertEqual(self.call('/export/document', body)[0], 400)
        body.update(endDate='2023-12-31')
        self.assertEqual(self.call('/export/document', body)[0], 400)


if __name__ == '__main__':
    unittest.main()
