from contextlib import redirect_stdout, redirect_stderr, closing
from io import BytesIO, StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import search, ai, local_api
from hope_archive.secure_store import SecretStoreError, WindowsCredentialStore


def diary(identity, body, day='2024-01-02', category='gratitude_diary'):
    return {'id': identity, 'note_date': day, 'diary_type': category, 'original_text': body,
            'title': '合成标题', 'comments': [{'items': [{'text': '留言测试'}]}],
            'emotion': {'identity': 'emotion_ha'}, 'weather': {'identity': 'weather_qing'}}


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'archive'; self.root.mkdir()
        self.source = self.root / 'processed/diaries.normalized.json'; self.source.parent.mkdir()
        self.index = search.SearchIndex(self.root, Path(self.tmp.name) / 'cache')

    def write(self, entries):
        self.source.write_text(json.dumps({'diaries': entries}), encoding='utf-8')

    def test_creation_keywords_filters_snippets_and_offline_detail(self):
        self.write([diary(1, '今天没去打乒乓球比赛，明天再去。'), diary(2, '参加乒乓球比赛', '2024-01-03', 'discovery_diary')])
        with patch('urllib.request.urlopen', side_effect=AssertionError('offline')):
            result = self.index.query('乒乓球')
            self.assertEqual(result['total'], 2)
            self.assertIn('乒乓球', result['items'][0]['snippet'])
            self.assertEqual(self.index.query('乒乓球', begin='2024-01-03')['total'], 1)
            self.assertEqual(self.index.query('乒乓球', end='2024-01-02')['total'], 1)
            self.assertEqual(self.index.query('乒乓球', category='gratitude_diary')['total'], 1)
            self.assertEqual(self.index.query('乒乓球', kind='capsule')['total'], 0)
            self.assertIn('乒乓球', self.index.detail(result['items'][0]['id'])['body'])
            for query in ('留言', '晴', '哈', '标题'):
                self.assertEqual(self.index.query(query)['total'], 2)
            self.assertEqual(self.index.query('没有这个词')['total'], 0)

    def test_incremental_updates_deleted_entries_and_rebuild(self):
        self.write([diary(1, '旧内容'), diary(2, '待删除内容')])
        self.assertEqual(self.index.sync()['updatedFiles'], 1)
        self.assertEqual(self.index.sync()['updatedFiles'], 0)
        self.write([diary(1, '新的更新内容')])
        self.assertEqual(self.index.query('旧内容')['total'], 0)
        self.assertEqual(self.index.query('待删除')['total'], 0)
        self.assertEqual(self.index.query('更新')['total'], 1)
        self.assertEqual(self.index.sync(rebuild=True)['entries'], 1)
        self.source.unlink()
        self.assertEqual(self.index.query('更新')['total'], 0)

    def test_empty_unusual_characters_and_literal_syntax(self):
        self.assertEqual(self.index.sync()['entries'], 0)
        self.write([]); self.assertEqual(self.index.query('空')['total'], 0)
        self.write([diary(1, '中文测试 <script> ABC 100% "quoted" OR something')])
        for q in ('中文', '中文测试', '<script>', 'abc', '100%', '"quoted"', 'OR'):
            self.assertEqual(self.index.query(q)['total'], 1, q)
        self.assertEqual(self.index.query('" OR missing')['total'], 0)
        with self.assertRaises(search.SearchError): self.index.query('x', begin='2024-02-30')
        with self.assertRaises(search.SearchError): self.index.query('x', begin='2024-02-02', end='2024-01-01')

    def test_capsule_scope_separate_kind_and_hidden_text(self):
        self.write([diary(1, '胶囊日记合成内容', category='capsule_diary')])
        path = self.root / 'processed/capsules.normalized.json'
        path.write_text(json.dumps({'capsules': [
            {'id': 'a', 'status': 'opened', 'content': '时间胶囊合成内容', 'created_at': '2024-01-03', 'metadata': {}},
            {'id': 'b', 'status': 'unopened', 'content': '不可搜索秘密', 'metadata': {}},
            {'id': 'c', 'status': 'opened', 'content': '已清空秘密', 'metadata': {'status': -1}}]}), encoding='utf-8')
        self.assertEqual(self.index.query('合成内容')['total'], 2)
        self.assertEqual(self.index.query('合成内容', kind='capsule')['total'], 1)
        self.assertEqual(self.index.query('秘密')['total'], 0)
        self.assertEqual(self.index.query('合成内容', category='capsule_diary')['total'], 1)

    def test_invalid_file_rolls_back_and_missing_detail(self):
        self.write([diary(1, 'valid')]); self.index.sync()
        self.source.write_text('broken', encoding='utf-8')
        with self.assertRaises(search.SearchError): self.index.sync(rebuild=True)
        with closing(sqlite3.connect(self.index.path)) as db: self.assertEqual(db.execute('select count(*) from entries').fetchone()[0], 1)
        self.write([])
        with self.assertRaises(search.SearchError): self.index.detail('missing')

    def test_local_search_without_hope_login(self):
        self.write([diary(1, '离线测试')])
        service = local_api.LocalService(); self.addCleanup(service.pool.shutdown)
        service.search_cache = Path(self.tmp.name) / 'service-cache'
        with patch('hope_archive.auth.login_by_password', side_effect=AssertionError('No Hope login')):
            result = service.dispatch('POST', '/search/query', {'root': str(self.root), 'query': '离线'}, '')
            self.assertEqual(result['total'], 1)
            detail = service.dispatch('POST', '/search/detail', {'root': str(self.root), 'id': result['items'][0]['id']}, '')
            self.assertIn('离线', detail['body'])


class FakeStore:
    def __init__(self): self.values = {}
    def read(self, name): return self.values.get(name)
    def write(self, name, value): self.values[name] = value
    def delete(self, name): self.values.pop(name, None)


class AITests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore(); self.settings = ai.AISettings(self.store)
        self.body = {'provider': 'openai', 'model': 'fixture-model', 'apiKey': 'synthetic-not-a-real-key'}

    def test_secure_save_metadata_replace_delete_and_no_plaintext(self):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output), patch.object(Path, 'write_text', side_effect=AssertionError('No plaintext file')):
            result = self.settings.save(self.body)
            self.assertTrue(result['configured'])
            self.assertNotIn(self.body['apiKey'], json.dumps(result))
            self.assertNotIn('apiKey', result)
            self.settings.save(dict(self.body, apiKey='synthetic-replacement'))
            self.assertEqual(json.loads(self.store.values['openai'])['apiKey'], 'synthetic-replacement')
            self.assertFalse(self.settings.delete('openai')['configured'])
            self.assertFalse(self.settings.metadata('openai')['configured'])
        self.assertEqual(output.getvalue(), '')

    def test_validation_custom_model_and_endpoint_binding(self):
        for body in [dict(self.body, provider='unknown'), dict(self.body, baseUrl='https://different.example/v1'), dict(self.body, model='bad model')]:
            with self.assertRaises(ai.AIError): self.settings.save(body)
        for url in ['http://example.invalid/v1', 'https://user:pass@example.invalid', 'https://example.invalid?key=fixture', 'file:///tmp', 'https://example.invalid/#fragment']:
            with self.assertRaises(ai.AIError): self.settings.save(dict(self.body, provider='custom', baseUrl=url))
        custom = dict(self.body, provider='custom', baseUrl='https://example.invalid/v1', model='new-provider/custom-model')
        self.settings.save(custom)
        self.settings.save(dict(custom, apiKey='', model='another-new-model'))
        with self.assertRaises(ai.AIError): self.settings.test(dict(custom, apiKey='', baseUrl='https://elsewhere.invalid/v1'))
        self.assertFalse(self.settings.metadata('gemini')['configured'])

    def test_models_test_has_no_archive_or_generation_and_no_echo(self):
        with patch.object(ai, 'build_opener') as opener:
            opener.return_value.open.return_value = BytesIO(b'{"data":[{"id":"fixture-model"}],"private":"should-not-return"}')
            result = self.settings.test(self.body)
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, 'https://api.openai.com/v1/models')
            self.assertEqual(req.get_method(), 'GET'); self.assertIsNone(req.data)
            self.assertTrue(result['modelListed'])
            self.assertNotIn('should-not-return', json.dumps(result))
            self.assertNotIn(self.body['apiKey'], json.dumps(result))
        self.assertFalse(self.settings.metadata('openai')['configured'])

    def test_provider_errors_no_secret_echo_and_redirect_block(self):
        for failure in [URLError(self.body['apiKey']), HTTPError('https://fixture.invalid', 401, self.body['apiKey'], {}, BytesIO(b'private response'))]:
            with patch.object(ai, 'build_opener') as opener:
                opener.return_value.open.side_effect = failure
                with self.assertRaises(ai.AIError) as caught: self.settings.test(self.body)
                self.assertNotIn(self.body['apiKey'], str(caught.exception))
                self.assertIsInstance(opener.call_args.args[0], ai._NoAuthRedirect)
                opener.return_value.open.assert_called_once()

    def test_secure_storage_unavailable_fails_closed(self):
        with patch('hope_archive.secure_store.sys.platform', 'linux'):
            with self.assertRaises(SecretStoreError): WindowsCredentialStore()
        with patch.object(self.store, 'write', side_effect=SecretStoreError('Unavailable')):
            with self.assertRaises(SecretStoreError): self.settings.save(self.body)
        self.assertFalse(self.store.values)

    def test_local_routes_never_return_key_and_no_chat_route(self):
        service = local_api.LocalService(); self.addCleanup(service.pool.shutdown); service.ai_settings = self.settings
        result = service.dispatch('POST', '/ai/save', self.body, '')
        self.assertNotIn(self.body['apiKey'], json.dumps(result))
        self.assertTrue(service.dispatch('POST', '/ai/status', {'provider': 'openai'}, '')['configured'])
        self.assertFalse(service.dispatch('POST', '/ai/delete', {'provider': 'openai'}, '')['configured'])
        with self.assertRaises(local_api.RequestError): service.dispatch('POST', '/ai/chat', {}, '')
