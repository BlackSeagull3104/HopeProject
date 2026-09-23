import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from hope_archive.ai_assistant import (
    DiaryAssistant, MAX_CONTEXT_CHARS, MAX_HISTORY_TURNS, build_messages,
    query_terms,
)
from hope_archive.search import SearchIndex


class FakeSettings:
    def __init__(self):
        self.calls = []

    def configured(self):
        return [{'provider': 'mock', 'label': 'Mock', 'configured': True,
                 'model': 'fixture-model', 'baseUrl': 'https://example.invalid/v1'}]

    def chat(self, provider, messages):
        self.calls.append((provider, messages))
        return '基于检索片段的测试回答。[来源 1]'


def diary(identity, day, title, body, kind='discovery_diary'):
    return {'id': identity, 'note_date': day, 'title': title, 'diary_type': kind,
            'original_text': body, 'content': [], 'comments': [],
            'author': {'id': 'synthetic-user'}}


class DiaryAssistantTests(unittest.TestCase):
    def setUp(self):
        self.root_tmp = TemporaryDirectory()
        self.cache_tmp = TemporaryDirectory()
        self.root = Path(self.root_tmp.name)
        entries = [
            diary('d1', '2026-01-03', '自然语言处理', '今天学习 NLP，并整理了 tokenizer 笔记。'),
            diary('d2', '2026-02-14', '贵州旅行', '登上梵净山看云海，晚上回到贵阳。', 'gratitude_diary'),
            diary('d3', '2026-03-08', '模型实验', '阅读 nanoGPT 源码并训练了一个小模型。'),
            diary('d4', '2026-03-09', '继续学习', '学习了 Python 并完成课程练习。'),
            diary('d5', '2026-03-10', '长日记', ('无关前言。\n' * 600) + '末尾记录了稀有词量子花园。'),
            diary('d6', '2026-03-11', '第二次 NLP 课', '复习 NLP 和 HMM，然后去打乒乓球。'),
            diary('d7', '2026-03-12', '晚餐', '晚饭吃了贵州酸汤鱼，但没有旅行。'),
            diary('d8', '2026-03-13', '重复摘录', '阅读 nanoGPT 源码并训练了一个小模型。'),
            diary('d9', '2026-01-03', '午餐', '中午吃了面条。'),
        ]
        document = {'schema_version': 1, 'source': 'synthetic', 'diaries': entries}
        (self.root / 'diaries.normalized.json').write_text(
            json.dumps(document, ensure_ascii=False), encoding='utf-8')
        self.settings = FakeSettings()
        self.index = SearchIndex(self.root, Path(self.cache_tmp.name))
        self.assistant = DiaryAssistant(self.index, self.settings)

    def tearDown(self):
        self.root_tmp.cleanup()
        self.cache_tmp.cleanup()

    def ask(self, question, **extra):
        return self.assistant.ask({'question': question, 'provider': 'mock',
                                   'disclosureAccepted': True, **extra})

    def test_chinese_english_alias_and_mixed_retrieval(self):
        for question, expected in [
                ('我什么时候写过 NLP？', '自然语言处理'),
                ('自然语言处理学了什么？', '自然语言处理'),
                ('nanoGPT tokenizer 在哪篇日记？', '模型实验'),
                ('贵州的梵净山旅行是什么时候？', '贵州旅行')]:
            result = self.ask(question)
            self.assertTrue(result['providerCalled'])
            self.assertIn(expected, [source['title'] for source in result['sources']])

    def test_natural_question_and_filters(self):
        result = self.ask('我最近学了什么？', beginDate='2026-03-01', endDate='2026-03-31')
        self.assertEqual(result['sources'][0]['title'], '继续学习')
        filtered = self.ask('梵净山', diaryType='gratitude_diary')
        self.assertEqual([source['title'] for source in filtered['sources']], ['贵州旅行'])

    def test_multiple_dates_duplicates_and_follow_up(self):
        result = self.ask('哪几天提到 NLP？')
        self.assertEqual({item['date'] for item in result['sources']}, {'2026-01-03', '2026-03-11'})
        duplicate = self.ask('nanoGPT')
        self.assertEqual(len(duplicate['sources']), 2)
        follow_up = self.ask('那一天我还写了什么？', history=[
            {'role': 'user', 'content': '我最近什么时候提到过 NLP？'},
            {'role': 'assistant', 'content': '你在两篇日记中提到过。'},
        ])
        self.assertTrue(follow_up['providerCalled'])
        self.assertIn('第二次 NLP 课', [item['title'] for item in follow_up['sources']])

    def test_unrelated_question_does_not_call_provider(self):
        before = len(self.settings.calls)
        result = self.ask('上海迪士尼烟花几点开始？')
        self.assertFalse(result['providerCalled'])
        self.assertEqual(result['sources'], [])
        self.assertEqual(len(self.settings.calls), before)
        self.assertIn('没有找到足够信息', result['answer'])

    def test_context_is_bounded_and_contains_no_internal_paths_or_secrets(self):
        result = self.ask('量子花园', history=[
            {'role': 'user' if i % 2 == 0 else 'assistant', 'content': f'history-{i}'}
            for i in range(10)
        ])
        self.assertLessEqual(result['contextChars'], MAX_CONTEXT_CHARS)
        messages = self.settings.calls[-1][1]
        self.assertLessEqual(len(messages) - 2, MAX_HISTORY_TURNS)
        serialized = json.dumps(messages, ensure_ascii=False)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn('apiKey', serialized)
        self.assertNotIn('secret', serialized)
        self.assertLessEqual(len(result['sources']), 8)

    def test_status_is_safe_and_source_ids_are_stable_without_duplicates(self):
        status = self.assistant.status()
        self.assertNotIn('apiKey', json.dumps(status))
        first = self.ask('NLP')
        second = self.ask('NLP')
        self.assertEqual(first['sources'][0]['id'], second['sources'][0]['id'])
        self.assertEqual(len({item['id'] for item in first['sources']}), len(first['sources']))

    def test_disclosure_and_history_validation(self):
        with self.assertRaisesRegex(Exception, '隐私说明'):
            self.assistant.ask({'question': 'NLP', 'provider': 'mock'})
        messages = build_messages('NLP', [], [
            {'role': 'user', 'content': 'ok'},
            {'role': 'tool', 'content': 'ignored'},
            {'role': 'assistant', 'content': 'x' * 2001},
        ])
        self.assertEqual([item['content'] for item in messages[1:-1]], ['ok'])

    def test_query_expansion_is_deterministic(self):
        self.assertEqual(query_terms('自然语言处理 NLP'), query_terms('自然语言处理 NLP'))
        self.assertIn('NLP', query_terms('自然语言处理 NLP'))

    def test_follow_up_uses_cited_source_then_same_day_then_broadens(self):
        first = self.ask('NLP')
        cited = next(s['id'] for s in first['sources'] if s['date'] == '2026-01-03')
        locked = self.ask('那一天我还写了什么？', sourceIds=[cited])
        self.assertEqual([s['title'] for s in locked['sources']], ['自然语言处理'])
        same_day = self.ask('那天吃了什么？', sourceIds=[cited])
        self.assertEqual([s['title'] for s in same_day['sources']], ['午餐'])
        broader = self.ask('那天贵州', sourceIds=[cited])
        self.assertIn('贵州旅行', [s['title'] for s in broader['sources']])

    def test_development_diagnostics_are_off_by_default(self):
        from hope_archive.ai_assistant import development_diagnostics
        from unittest.mock import patch
        with patch.dict('os.environ', {'HOPE_AI_DEBUG': ''}):
            with self.assertRaisesRegex(Exception, '诊断'):
                development_diagnostics(self.index, 'NLP')
        with patch.dict('os.environ', {'HOPE_AI_DEBUG': '1'}):
            result = development_diagnostics(self.index, 'NLP')
            self.assertGreater(result['candidateCount'], 0)
            self.assertNotIn(str(self.root), json.dumps(result))

    def test_empty_archive_is_clear_and_skips_provider(self):
        with TemporaryDirectory() as root, TemporaryDirectory() as cache:
            settings = FakeSettings()
            assistant = DiaryAssistant(SearchIndex(root, Path(cache)), settings)
            result = assistant.ask({'question': 'NLP', 'provider': 'mock',
                                    'disclosureAccepted': True})
            self.assertIn('请先完成日记归档', result['answer'])
            self.assertFalse(result['providerCalled'])
            self.assertEqual(settings.calls, [])


if __name__ == '__main__':
    unittest.main()
