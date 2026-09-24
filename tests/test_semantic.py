"""Synthetic, offline integrity/index/privacy tests; never use account data."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from hope_archive import semantic_model as model
from hope_archive.semantic import (SemanticService, VectorIndex, RetrievalIndex,
    snapshot, fuse, FALLBACK)
from hope_archive.search import SearchIndex
from hope_archive.ai_assistant import DiaryAssistant, query_terms
from hope_archive.ai_workflows import WorkflowManager


class FakeEncoder:
    def __init__(self): self.calls = []
    def __call__(self, text, kind):
        self.calls.append((text, kind))
        values = [0.] * 384
        values[0 if any(term in text for term in ('nanoGPT', '语言模型')) else 1] = 1.
        return [{'text': text, 'vector': values}]
    def close(self): pass


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / 'archive'; self.root.mkdir()
        self.path = self.root / 'diaries.normalized.json'
        self.entries = [dict(id=str(i), author={'id':'synthetic'}, note_date=f'2026-09-0{i+1}',
            diary_type='discovery_diary', original_text=text, content=[], comments=[])
            for i, text in enumerate(('今天继续跑 nanoGPT。', '今天去公园散步。', '明天准备学习 Python。'))]
        self.write()
        self.index = SearchIndex(self.root, self.home / 'fts')
        self.pool = ThreadPoolExecutor(max_workers=2); self.addCleanup(self.pool.shutdown)
        self.service = SemanticService(self.pool, self.home / 'semantic')
        self.addCleanup(self.service.close)
        self.encoder = FakeEncoder()
        self.derived = self.service.derived(self.index)

    def write(self): self.path.write_text(json.dumps({'diaries': self.entries}), encoding='utf-8')
    def ready(self):
        self.derived.sync(snapshot(self.index), self.encoder)
        self.addCleanup(patch.stopall)
        patch.object(self.service, 'encoder', return_value=self.encoder).start()
        patch.object(model, 'installed', return_value=self.home).start()
    def find(self, text, **kwargs):
        return RetrievalIndex(self.index, self.service, 'Hybrid').retrieve(text, query_terms(text), **kwargs)

    def test_fts_no_component_or_provider(self):
        with patch.object(self.service, 'encoder', side_effect=AssertionError):
            result = RetrievalIndex(self.index, self.service, 'FTS5').retrieve('nanoGPT', ['nanoGPT'])
        self.assertEqual(len(result), 1)
        self.assertEqual(self.service.status(self.index)['state'], 'not_installed')

    def test_missing_component_visible_fallback(self):
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        self.assertTrue(wrapped.retrieve('nanoGPT', ['nanoGPT']))
        self.assertEqual(wrapped.retrieval, {'mode':'FTS5','fallback':FALLBACK})

    def test_rrf_matches_experiment(self):
        self.assertEqual(fuse(['a','b'], ['b','c']), ['b','a','c'])
        self.assertEqual(fuse(['a','a'], ['b']), ['a','b'])

    def test_hybrid_semantic_and_exact(self):
        self.ready()
        self.assertIn('nanoGPT', self.find('语言模型')[0]['body'])
        self.assertIn('nanoGPT', self.find('nanoGPT')[0]['body'])

    def test_index_incremental_changes_deletion_and_dedup(self):
        entries = snapshot(self.index)
        self.assertEqual(self.derived.sync(entries, self.encoder), 3)
        self.assertEqual(self.derived.sync(entries, self.encoder), 0)
        self.entries[0]['original_text'] += ' 修订。'; self.entries.pop(); self.write()
        entries = snapshot(self.index)
        self.assertFalse(self.derived.ready(entries))
        self.assertEqual(self.derived.sync(entries, self.encoder), 1)
        with closing(self.derived.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM docs').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT count(*) FROM chunks').fetchone()[0], 2)
        self.assertEqual(len(self.encoder.calls), 4)

    def test_update_requires_rebuild_and_no_stale_results(self):
        self.ready()
        self.entries.pop(0); self.write()
        self.assertEqual(self.service.status(self.index)['state'], 'rebuild_required')
        self.assertEqual(self.find('nanoGPT'), [])

    def test_account_root_isolation(self):
        self.ready()
        other = self.home / 'other'; other.mkdir()
        index = SearchIndex(other, self.home / 'fts')
        self.assertNotEqual(self.derived.path, self.service.derived(index).path)
        self.assertEqual(RetrievalIndex(index, self.service, 'Hybrid').retrieve('nanoGPT',['nanoGPT']), [])

    def test_filters_before_semantic_and_fusion(self):
        self.ready()
        self.assertTrue(all(e['date'] == '2026-09-02' for e in self.find('语言模型', begin='2026-09-02',end='2026-09-02')))
        self.assertEqual(self.find('语言模型', category='gratitude_diary'), [])

    def test_corrupt_index_explicit_rebuild(self):
        self.derived.path.write_bytes(b'corrupt')
        with self.assertRaises(sqlite3.DatabaseError): self.derived.sync(snapshot(self.index), self.encoder)
        self.derived.sync(snapshot(self.index), self.encoder, rebuild=True)
        self.assertTrue(self.derived.ready(snapshot(self.index)))

    def test_version_mismatch_rebuild(self):
        self.ready()
        with patch.object(model, 'VERSION', 'new-version'):
            self.assertFalse(self.derived.ready(snapshot(self.index)))
            self.assertEqual(self.derived.sync(snapshot(self.index), self.encoder), 3)

    def test_failed_increment_is_transactional(self):
        self.derived.sync(snapshot(self.index), self.encoder)
        self.entries[0]['original_text'] += ' changed'; self.write()
        with closing(self.derived.connect()) as db: before = list(db.execute('SELECT * FROM docs'))
        with self.assertRaises(RuntimeError):
            self.derived.sync(snapshot(self.index), lambda *args: (_ for _ in ()).throw(RuntimeError()))
        with closing(self.derived.connect()) as db: self.assertEqual(before, list(db.execute('SELECT * FROM docs')))

    def test_load_failure_visible_fallback_no_paths(self):
        self.ready()
        self.service.encoder.side_effect = RuntimeError('private path and secret must not escape')
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        result = wrapped.related_query('nanoGPT',['nanoGPT'])
        self.assertTrue(result['items']); self.assertEqual(result['retrieval']['fallback'], FALLBACK)
        self.assertNotIn('private path', json.dumps(result))
        self.assertEqual(self.service.status(self.index)['state'], 'index_failed')

    def test_invalid_vector_fallback(self):
        self.ready()
        with closing(self.derived.connect()) as db, db:
            db.execute("UPDATE chunks SET vector=x'00'")
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        self.assertTrue(wrapped.retrieve('nanoGPT',['nanoGPT']))
        self.assertEqual(wrapped.retrieval['mode'], 'FTS5')

    def test_missing_chunks_fallback(self):
        self.ready()
        with closing(self.derived.connect()) as db, db: db.execute('DELETE FROM chunks')
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        self.assertTrue(wrapped.retrieve('nanoGPT',['nanoGPT']))
        self.assertEqual(wrapped.retrieval['mode'],'FTS5')

    def test_index_metadata_contains_no_paths_or_credentials(self):
        self.ready()
        with closing(self.derived.connect()) as db: data = dict(db.execute('SELECT * FROM meta'))
        self.assertEqual(set(data), {'schema','model','version','dimension','scope'})
        self.assertNotIn(str(self.root), json.dumps(data))
        self.assertNotIn(str(self.root), json.dumps(self.service.status(self.index)))

    def test_local_no_network_no_provider(self):
        self.ready()
        with patch('urllib.request.urlopen', side_effect=AssertionError), patch('hope_archive.ai.AISettings.chat', side_effect=AssertionError):
            self.assertTrue(self.find('语言模型'))

    def test_ask_hybrid_citations_and_consent(self):
        self.ready()
        class Settings:
            def chat(self, provider, messages):
                assert len(messages[-1]['content']) < 14000
                return '合成回答'
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        result = DiaryAssistant(wrapped, Settings()).ask({'question':'语言模型','provider':'mock','disclosureAccepted':True})
        self.assertTrue(result['sources'])
        self.assertEqual(result['sources'][0]['id'], self.find('语言模型')[0]['id'])
        self.assertEqual(wrapped.retrieval['mode'], 'Hybrid')

    def test_selected_review_do_not_retrieve_broadly(self):
        self.ready()
        class Settings:
            def configured(self): return [{'provider':'mock','label':'Mock','model':'synthetic'}]
        manager = WorkflowManager(self.pool)
        wrapped = RetrievalIndex(self.index, self.service, 'Hybrid')
        chosen = snapshot(self.index)[0]['id']
        with patch.object(wrapped, 'retrieve', side_effect=AssertionError):
            result = manager.prepare('a',wrapped,Settings(),{'mode':'selected','question':'总结',
                'sourceIds':[chosen],'provider':'mock','disclosureAccepted':True})
            self.assertEqual(result['diaryCount'],1)
            plan = manager.get('a',result['id'])
            self.assertEqual([s['id'] for s in plan['sources']], [chosen])
            result = manager.prepare('a',wrapped,Settings(),{'mode':'review','beginDate':'2026-09-02',
                'endDate':'2026-09-02','provider':'mock','disclosureAccepted':True})
            self.assertEqual(result['diaryCount'],1)

    def test_background_failure_states(self):
        with patch.object(model, 'install', side_effect=OSError):
            self.service.install_state = 'downloading'; self.service.run(self.index, True, False)
            self.assertEqual(self.service.status(self.index)['state'], 'download_failed')
        with patch.object(model, 'install', side_effect=model.IntegrityError):
            self.service.install_state = 'verifying'; self.service.run(self.index, True, False)
            self.assertEqual(self.service.status(self.index)['state'], 'verification_failed')
        self.service.install_state = ''
        with patch.object(self.service, 'encoder', side_effect=ValueError):
            self.service.run(self.index, False, False)
            self.assertEqual(self.service.status(self.index)['state'], 'index_failed')

    def test_source_bytes_unchanged(self):
        before = self.path.read_bytes(); self.ready(); self.find('语言模型')
        self.assertEqual(before, self.path.read_bytes())

    def test_api_explicit_install_and_mode_validation(self):
        from hope_archive.desktop_api import DesktopService
        from hope_archive.local_api import RequestError
        service = DesktopService(self.home / 'profile')
        self.addCleanup(service.pool.shutdown)
        service.dispatch('POST','/settings/read',{},None)
        (service.library.root / 'diaries.normalized.json').write_bytes(self.path.read_bytes())
        status = service.dispatch('POST','/library/semantic/status',{},None)
        self.addCleanup(service.semantic_service.close)
        self.assertEqual(status['state'],'not_installed')
        with patch.object(service.semantic_service,'start',return_value=status) as start:
            for body in ({},{'confirmed':False},{'confirmed':'true'}):
                with self.assertRaises(RequestError): service.dispatch('POST','/library/semantic/install',body,None)
            start.assert_not_called()
            service.dispatch('POST','/library/semantic/install',{'confirmed':True},None)
            self.assertEqual(start.call_count,1)
        result = service.dispatch('POST','/library/search/query',{'query':'nanoGPT','contentType':'diary','retrievalMode':'Hybrid'},None)
        self.assertTrue(result['items']); self.assertEqual(result['retrieval']['mode'],'FTS5')
        with self.assertRaises(RequestError):
            service.dispatch('POST','/library/search/query',{'query':'NLP','retrievalMode':'Embedding'},None)

    def test_api_ask_fallback_and_timeline_order(self):
        self.ready()
        class Settings:
            def configured(self): return [{'provider':'mock','label':'Mock','model':'synthetic'}]
            def chat(self,*args): return '合成回答'
        manager = WorkflowManager(self.pool)
        wrapped = RetrievalIndex(self.index,self.service,'Hybrid')
        result = manager.prepare('a',wrapped,Settings(),{'mode':'timeline','question':'语言模型',
            'provider':'mock','beginDate':'2026-09-02','endDate':'2026-09-03','disclosureAccepted':True})
        dates = [s['date'] for s in manager.get('a',result['id'])['sources']]
        self.assertEqual(dates, sorted(dates)); self.assertNotIn('2026-09-01',dates)
        with patch.object(self.service,'status',return_value={'state':'not_installed'}):
            answer = DiaryAssistant(wrapped,Settings()).ask({'question':'nanoGPT','provider':'mock','disclosureAccepted':True})
        self.assertTrue(answer['providerCalled']); self.assertEqual(wrapped.retrieval['mode'],'FTS5')


class DownloadTests(unittest.TestCase):
    def test_atomic_success_and_digest_failure(self):
        data = b'synthetic model'
        files = {'model.onnx':('model.onnx',len(data),hashlib.sha256(data).hexdigest())}
        class Response(io.BytesIO): url = 'https://synthetic.invalid/model'
        with TemporaryDirectory() as folder, patch.object(model, 'FILES', files):
            states = []
            with patch.object(model, 'urlopen', return_value=Response(data)):
                directory = model.install(folder, states.append)
            self.assertEqual(states, ['downloading','verifying'])
            self.assertEqual(directory, model.installed(folder)); model.verify(directory)
            with patch.object(model, 'urlopen', return_value=Response(b'x' * len(data))):
                with self.assertRaises(model.IntegrityError): model.install(folder, states.append)
            self.assertEqual(directory, model.installed(folder))
            self.assertFalse(list(Path(folder).glob('download-*')))

    def test_download_failure_never_installed(self):
        with TemporaryDirectory() as folder, patch.object(model, 'urlopen', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError): model.install(folder, lambda state: None)
            self.assertIsNone(model.installed(folder))

    def test_pointer_traversal_rejected(self):
        with TemporaryDirectory() as folder:
            (Path(folder)/'current').write_text('../secrets')
            with self.assertRaises(model.IntegrityError): model.installed(folder)
