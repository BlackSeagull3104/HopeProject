import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

from hope_archive.ai import AIError
from hope_archive.ai_workflows import WorkflowManager, valid_citations, dated_citations
from hope_archive.search import SearchIndex
from hope_archive.ai_assistant import query_terms


class MockSettings:
    def __init__(self):
        self.calls = []
        self.fail_at = None
        self.block = None

    def configured(self):
        return [{'provider': 'mock', 'label': 'Synthetic Model', 'model': 'fixture-model'}]

    def chat(self, provider, messages):
        self.calls.append((provider, messages))
        if self.block: self.block.wait(timeout=2)
        if self.fail_at == len(self.calls): raise AIError('无法连接服务商，请检查网络及 API 地址。')
        return f'合成摘要 {len(self.calls)} [来源 1]'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'archive'
        self.archive.mkdir()
        self.entries = []
        for i in range(24):
            topic = 'NLP 课程' if i % 3 == 0 else '贵州 梵净山 旅行' if i % 3 == 1 else '乒乓球和晚饭'
            self.entries.append({'id': f'd{i}', 'author': {'id': 'synthetic'},
                'note_date': f'2026-09-{i+1:02d}', 'diary_type': 'discovery_diary',
                'title': f'第{i+1}天 {topic}', 'original_text': f'合成测试内容：{topic}。',
                'content': [], 'comments': []})
        self.write()
        self.index = SearchIndex(self.archive, self.root / 'cache')
        self.settings = MockSettings()
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.addCleanup(self.pool.shutdown)
        self.manager = WorkflowManager(self.pool)

    def write(self):
        (self.archive / 'diaries.normalized.json').write_text(
            json.dumps({'schema_version': 1, 'diaries': self.entries}, ensure_ascii=False), encoding='utf-8')

    def prepare(self, mode='review', **extra):
        return self.manager.prepare('synthetic', self.index, self.settings, {
            'mode': mode, 'provider': 'mock', 'disclosureAccepted': True,
            'beginDate': '2026-09-01', 'endDate': '2026-09-30', **extra})

    def finish(self, plan_id):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            state = self.manager.get('synthetic', plan_id)['state']
            if state != 'running': return state
            time.sleep(.01)
        self.fail('Synthetic workflow did not finish')

    def test_small_review_uses_one_call_and_keeps_sources(self):
        plan = self.prepare(endDate='2026-09-02')
        self.assertEqual((plan['diaryCount'], plan['calls'], plan['large']), (2, 1, False))
        self.manager.start('synthetic', plan['id'], self.settings)
        self.assertEqual(self.finish(plan['id']), 'completed')
        result = self.manager.public(self.manager.get('synthetic', plan['id']))
        self.assertEqual(len(result['sources']), 2)
        self.assertEqual(len(self.settings.calls), 1)
        self.assertNotIn(str(self.root), json.dumps(self.settings.calls, ensure_ascii=False))

    def test_large_review_batches_hierarchically_and_requires_confirmation(self):
        plan = self.prepare()
        self.assertEqual(plan['diaryCount'], 24)
        self.assertGreater(plan['calls'], 2)
        self.assertTrue(plan['large'])
        with self.assertRaisesRegex(Exception, '确认'):
            self.manager.start('synthetic', plan['id'], self.settings)
        self.manager.start('synthetic', plan['id'], self.settings, True)
        self.assertEqual(self.finish(plan['id']), 'completed')
        self.assertEqual(len(self.settings.calls), plan['calls'])
        result = self.manager.public(self.manager.get('synthetic', plan['id']))
        self.assertEqual(len(result['sources']), 24)
        self.assertEqual(len({s['id'] for s in result['sources']}), 24)
        self.assertLessEqual(max(len(m[-1]['content']) for _, m in self.settings.calls), 12000)

    def test_timeline_filters_relevance_then_sorts_dates(self):
        plan = self.prepare('timeline', question='NLP')
        record = self.manager.get('synthetic', plan['id'])
        dates = [s['date'] for s in record['sources']]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), 8)
        self.assertTrue(all('NLP' in c['text'] for batch in record['batches'] for c in batch))

    def test_timeline_reports_relevance_cap(self):
        for i in range(60):
            self.entries.append({'id': f'extra-{i}', 'author': {'id': 'synthetic'},
                'note_date': f'2026-08-{i % 28 + 1:02d}', 'diary_type': 'discovery_diary',
                'title': 'NLP 补充记录', 'original_text': '合成 NLP 内容。'})
        self.write()
        plan = self.prepare('timeline', question='NLP', beginDate='2026-08-01')
        self.assertTrue(plan['truncated'])
        self.assertEqual(plan['diaryCount'], 50)

    def test_selected_ids_isolate_context_and_reject_invalid(self):
        ids = [entry['id'] for entry in self.index.range_entries('2026-09-01', '2026-09-02')]
        plan = self.prepare('selected', question='总结这些日记', sourceIds=ids)
        self.manager.start('synthetic', plan['id'], self.settings)
        self.assertEqual(self.finish(plan['id']), 'completed')
        sent = json.dumps(self.settings.calls, ensure_ascii=False)
        self.assertIn('第1天', sent)
        self.assertNotIn('第3天', sent)
        with self.assertRaisesRegex(Exception, '所选日记'):
            self.prepare('selected', question='总结', sourceIds=['f' * 64])

    def test_no_evidence_skips_model(self):
        for mode, extra in [('review', {'beginDate': '2025-01-01', 'endDate': '2025-01-31'}),
                            ('timeline', {'question': '上海迪士尼'})]:
            plan = self.prepare(mode, **extra)
            self.assertEqual(plan['calls'], 0)
            self.manager.start('synthetic', plan['id'], self.settings)
            self.assertEqual(self.finish(plan['id']), 'completed')
            self.assertEqual(self.manager.get('synthetic', plan['id'])['sources'], [])
        self.assertEqual(self.settings.calls, [])

    def test_retry_preserves_completed_batches(self):
        plan = self.prepare()
        self.settings.fail_at = 2
        self.manager.start('synthetic', plan['id'], self.settings, True)
        self.assertEqual(self.finish(plan['id']), 'failed')
        completed = len(self.manager.get('synthetic', plan['id'])['results'])
        self.assertEqual(completed, 1)
        self.settings.fail_at = None
        self.manager.start('synthetic', plan['id'], self.settings, True)
        self.assertEqual(self.finish(plan['id']), 'completed')
        self.assertEqual(len(self.settings.calls), plan['calls'] + 1)

    def test_cancel_stops_subsequent_batches(self):
        import threading
        self.settings.block = threading.Event()
        plan = self.prepare()
        self.manager.start('synthetic', plan['id'], self.settings, True)
        deadline = time.monotonic() + 2
        while not self.settings.calls and time.monotonic() < deadline: time.sleep(.01)
        self.manager.cancel('synthetic', plan['id'])
        self.settings.block.set()
        time.sleep(.05)
        self.assertEqual(self.manager.get('synthetic', plan['id'])['state'], 'cancelled')
        self.assertEqual(len(self.settings.calls), 1)

    def test_topics_and_export_are_source_linked_and_derivative(self):
        plan = self.prepare(lens='topics', endDate='2026-09-07')
        self.assertTrue(any(t['topic'] == 'NLP' and t['count'] == 3 for t in self.manager.get('synthetic', plan['id'])['topics']))
        self.manager.start('synthetic', plan['id'], self.settings, True)
        self.assertEqual(self.finish(plan['id']), 'completed')
        destination = self.root / 'user-selected' / 'archive'
        result = self.manager.export('synthetic', plan['id'], destination)
        path = Path(result['path'])
        self.assertEqual(path.parent, destination / 'AI回顾')
        output = path.read_text(encoding='utf-8')
        self.assertIn('AI 生成摘要', output)
        self.assertIn('2026-09-01', output)
        self.assertIn('Synthetic Model / fixture-model', output)
        self.assertNotIn(str(self.archive), output)
        self.assertNotIn('apiKey', output)
        self.assertNotIn('来源ID', output)
        first_id = self.manager.get('synthetic', plan['id'])['sources'][0]['id']
        self.assertNotIn(first_id[:12], output)

    def test_unknown_model_citation_is_removed(self):
        source = self.index.range_entries('2026-09-01', '2026-09-01')[0]
        marker = source['id'][:12]
        value = valid_citations(f'有证据 [来源 {marker}]；无证据 [来源 fabricated]。',
            [{'id': source['id']}])
        self.assertIn(f'[来源 {marker}]', value)
        self.assertNotIn('fabricated', value)
        self.assertIn('[2026-09-01]', dated_citations(value, [{'id': source['id'], 'date': source['date']}]))

    def test_malformed_and_duplicate_entries_do_not_expand_sources(self):
        self.entries.append(dict(self.entries[0]))
        self.entries.append({'id': 'blank', 'author': {'id': 'synthetic'},
            'note_date': '2026-09-25', 'diary_type': 'discovery_diary', 'content': []})
        self.write()
        plan = self.prepare()
        self.assertEqual(plan['diaryCount'], 24)
        self.assertEqual(len(self.manager.get('synthetic', plan['id'])['sources']), 24)


class SemanticBenchmarkTests(unittest.TestCase):
    def test_exact_alias_and_semantic_mismatch_recall(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            entries = [
                {'id': 'a', 'note_date': '2026-09-01', 'diary_type': 'discovery_diary', 'original_text': '今天继续跑 nanoGPT。'},
                {'id': 'b', 'note_date': '2026-09-02', 'diary_type': 'discovery_diary', 'original_text': '下午一直在调 tokenizer。'},
                {'id': 'c', 'note_date': '2026-09-03', 'diary_type': 'discovery_diary', 'original_text': '去梵净山坐了索道。'},
                {'id': 'd', 'note_date': '2026-09-04', 'diary_type': 'discovery_diary', 'original_text': '复习 NLP 课程。'},
            ]
            (root / 'diaries.normalized.json').write_text(json.dumps({'diaries': entries}, ensure_ascii=False), encoding='utf-8')
            index = SearchIndex(root, root / 'cache')
            cases = [
                ('nanoGPT', True), ('tokenizer', True), ('梵净山', True),
                ('自然语言处理', True), ('贵州', True),
                ('最近有没有训练语言模型？', False), ('我什么时候处理过文本编码？', False),
                ('我最近去过什么山？', False),
            ]
            for question, expected in cases:
                with self.subTest(question=question):
                    self.assertEqual(bool(index.retrieve(question, query_terms(question))), expected)


class WorkflowApiTests(unittest.TestCase):
    def test_search_to_ai_handoff_and_account_isolation(self):
        from hope_archive.desktop_api import DesktopService
        from hope_archive.local_api import RequestError
        with TemporaryDirectory() as folder:
            home = Path(folder) / 'profile'
            service = DesktopService(home)
            try:
                service.dispatch('POST', '/settings/read', {}, None)
                service.ai_settings = MockSettings()
                account = service.library.account_root('user-a')
                document = {'diaries': [{'id': 'one', 'author': {'id': 'user-a'},
                    'note_date': '2026-09-01', 'diary_type': 'discovery_diary',
                    'title': 'NLP 课', 'original_text': '今天学习 NLP。'}]}
                (account / 'diaries.normalized.json').write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
                service.sessions['token-a'] = {'userId': 'user-a', 'expires': time.monotonic() + 60}
                service.sessions['token-b'] = {'userId': 'user-b', 'expires': time.monotonic() + 60}
                call = lambda path, body, token='token-a': service.dispatch('POST', path, body, token)
                source_id = call('/library/search/query', {'query': 'NLP'})['items'][0]['id']
                plan = call('/library/ai/prepare', {'mode': 'selected', 'sourceIds': [source_id],
                    'question': '总结这篇', 'provider': 'mock', 'disclosureAccepted': True})
                self.assertEqual(plan['diaryCount'], 1)
                with self.assertRaises(RequestError):
                    call('/library/ai/prepare', {'mode': 'selected', 'sourceIds': [source_id],
                        'question': '总结这篇', 'provider': 'mock', 'disclosureAccepted': True}, 'token-b')
                call('/library/ai/start', {'id': plan['id']})
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    status = call('/library/ai/progress', {'id': plan['id']})
                    if status['state'] != 'running': break
                    time.sleep(.01)
                self.assertEqual(status['state'], 'completed')
                self.assertEqual([s['id'] for s in status['sources']], [source_id])
                with self.assertRaises(RequestError): call('/library/ai/progress', {'id': plan['id']}, 'token-b')
            finally:
                service.pool.shutdown(wait=True)


if __name__ == '__main__': unittest.main()
