"""Synthetic-only v3 boundaries and frozen benchmark checks; no model download."""
from contextlib import closing
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hope_archive.ai_assistant import query_terms, lexical_terms, DiaryAssistant, development_diagnostics, AssistantError
from hope_archive.retrieval import confidence
from hope_archive.search import SearchIndex, SearchError

BENCH=Path(__file__).resolve().parents[1]/'benchmarks/retrieval_v3'
sys.path.insert(0,str(BENCH))
from corpus import dataset
from evaluate import metrics, evaluate
from embedding import MemoryIndex, fuse
from rewrite import retrieve as rewrite_retrieve, PROMPT


class RetrievalV3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'archive';self.root.mkdir()
        self.diaries,_=dataset()
        self.path=self.root/'diaries.normalized.json'
        self.write(self.diaries)
        self.index=SearchIndex(self.root,Path(self.tmp.name)/'cache')
        self.index.sync()

    def write(self,entries):
        self.path.write_text(json.dumps({'diaries':entries},ensure_ascii=False),encoding='utf-8')

    def find(self,q,**kwargs):
        return self.index.retrieve(q,query_terms(q),**kwargs)

    def test_frozen_dataset_and_v2_results(self):
        old=json.loads((BENCH/'baseline.json').read_text(encoding='utf-8'))
        now=evaluate()
        self.assertEqual(old['datasetSha256'],now['datasetSha256'])
        for strategy in ('literal','v2_alias'):
            self.assertEqual(old['strategies'][strategy]['results'],now['strategies'][strategy]['results'])
        for category in ('all','exact','alias','paraphrase','semantic','Chinese','English','mixed','date-filtered'):
            self.assertGreaterEqual(now['strategies']['v3_concepts']['metrics'][category]['recall@5'],
                                    old['strategies']['v2_alias']['metrics'][category]['recall@5'])

    def test_metric_denominators(self):
        result=metrics([{'ranked':['x','a','b'],'relevant':['a','b','c','d']}])
        self.assertEqual(result['recall@1'],0)
        self.assertEqual(result['recall@3'],.5)
        self.assertEqual(result['mrr'],.5)
        self.assertEqual(result['precision@5'],.4)

    def test_exact_alias_and_single_chinese(self):
        self.assertTrue(self.find('nanoGPT'))
        self.assertTrue(self.find('HMM'))
        self.assertTrue(self.find('BPE'))
        self.assertEqual(len(self.find('猫')),1)

    def test_semantic_chinese_english_mixed(self):
        for query,expected in [('语言模型训练','nanoGPT'),('trained language models','nanoGPT'),
                               ('我什么时候处理 token？','tokenizer'),('文本编码','tokenizer'),
                               ('最近爬了什么山？','梵净山')]:
            with self.subTest(query=query):
                self.assertTrue(any(expected in e['body'] for e in self.find(query)))

    def test_expansion_is_one_way_and_bounded(self):
        self.assertEqual(query_terms('nanoGPT'),lexical_terms('nanoGPT'))
        self.assertNotIn('运动',query_terms('乒乓球'))
        self.assertNotIn('NLP',query_terms('anlpx'))
        self.assertLessEqual(len(query_terms('运动 文本编码 自然语言处理 语言模型 BPE HMM 爬山')),20)

    def test_filters_and_same_search_ai_candidates(self):
        found=self.find('语言模型训练',begin='2026-09-01',end='2026-09-30')
        self.assertTrue(found)
        self.assertTrue(all(e['date'].startswith('2026-09') for e in found))
        self.assertEqual(self.find('语言模型训练',category='gratitude_diary'),[])
        result=self.index.related_query('语言模型训练',query_terms('语言模型训练'),'2026-09-01','2026-09-30')
        self.assertEqual([e['id'] for e in found],[e['id'] for e in result['items']])
        self.assertNotIn(str(self.root),json.dumps(result))
        with self.assertRaises(SearchError): self.index.related_query('NLP',['NLP'],offset=True)

    def test_account_and_selected_isolation(self):
        other=Path(self.tmp.name)/'other';other.mkdir()
        other_index=SearchIndex(other,Path(self.tmp.name)/'cache')
        self.assertEqual(other_index.retrieve('语言模型训练',query_terms('语言模型训练')),[])
        chosen=self.find('绿萝')[0]
        self.assertEqual([e['id'] for e in self.index.selected_entries([chosen['id']])],[chosen['id']])
        with self.assertRaises(SearchError):other_index.selected_entries([chosen['id']])

    def test_duplicate_long_and_rebuild_without_source_mutation(self):
        self.write(self.diaries+[self.diaries[0],{**self.diaries[1],'original_text':'合成前言。'*2000+' tokenizer'}])
        before=self.path.read_bytes();self.index.sync()
        self.assertEqual(self.index.diary_count(),60)
        self.assertTrue(self.find('tokenizer'))
        ids=[e['id'] for e in self.find('语言模型训练')]
        self.index.sync(rebuild=True)
        self.assertEqual(ids,[e['id'] for e in self.find('语言模型训练')])
        self.assertEqual(before,self.path.read_bytes())

    def test_old_fts_schema_works_without_migration(self):
        with closing(self.index.connect()) as db:
            schema=list(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
        self.find('文本编码')
        with closing(self.index.connect()) as db:
            self.assertEqual([tuple(r) for r in schema],[tuple(r) for r in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'")])

    def test_unlinked_ocr_is_not_silently_diary_evidence(self):
        from hope_archive.ocr import OCRJobs
        self.write([{**self.diaries[0],'ocr_text':'synthetic-unlinked-image-phrase'}])
        self.assertEqual(self.find('synthetic-unlinked-image-phrase'),[])
        with self.assertRaises(ValueError):
            OCRJobs().start([{'name':'synthetic.png','data':'','parentDiaryId':'d1'}])

    def test_related_api_offline_handoff_and_scope(self):
        from hope_archive.desktop_api import DesktopService
        from hope_archive.local_api import RequestError
        import time
        service=DesktopService(Path(self.tmp.name)/'profile');self.addCleanup(service.pool.shutdown)
        service.dispatch('POST','/settings/read',{},None)
        account=service.library.account_root('synthetic-v3')
        (account/'diaries.normalized.json').write_bytes(self.path.read_bytes())
        service.sessions['a']={'userId':'synthetic-v3','expires':time.monotonic()+60}
        service.sessions['b']={'userId':'other','expires':time.monotonic()+60}
        body={'query':'语言模型训练','related':True,'contentType':'diary'}
        with patch('urllib.request.urlopen',side_effect=AssertionError('Must stay offline')):
            result=service.dispatch('POST','/library/search/query',body,'a')
            self.assertTrue(result['items'])
            self.assertEqual(service.dispatch('POST','/library/search/query',body,'b')['total'],0)
            source=service.dispatch('POST','/library/search/detail',{'id':result['items'][0]['id']},'a')
            self.assertIn('body',source)
            with self.assertRaises(RequestError):
                service.dispatch('POST','/library/search/query',{**body,'contentType':'capsule'},'a')
            with self.assertRaises(RequestError):
                service.dispatch('POST','/library/search/query',{**body,'related':'true'},'a')
        self.assertNotIn(str(account),json.dumps(result))

    def test_no_evidence_no_model_call(self):
        class Never:
            def chat(self,*args):raise AssertionError('Unexpected model call')
        result=DiaryAssistant(self.index,Never()).ask({'question':'宇宙边界不存在的合成词','provider':'mock','disclosureAccepted':True})
        self.assertFalse(result['providerCalled'])

    def test_confidence_is_coverage_not_probability(self):
        self.assertEqual(confidence('NLP',self.find('NLP')),'strong')
        self.assertEqual(confidence('语言模型训练',self.find('语言模型训练')),'weak')
        self.assertEqual(confidence('不存在',[]),'none')

    def test_diagnostics_require_development_opt_in(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(AssistantError):development_diagnostics(self.index,'NLP')
        with patch.dict('os.environ',{'HOPE_AI_DEBUG':'1'}),patch.object(sys,'frozen',True,create=True):
            with self.assertRaises(AssistantError):development_diagnostics(self.index,'NLP')
        with patch.dict('os.environ',{'HOPE_AI_DEBUG':'1'}):
            result=development_diagnostics(self.index,'文本编码')
        self.assertNotIn(str(self.root),json.dumps(result))
        self.assertNotIn('body',result)
        self.assertEqual(result['confidence'],'weak')

    def test_rewrite_opt_in_and_strong_skip(self):
        def never(*args):raise AssertionError('Unexpected rewrite')
        for kwargs in ({},{'enabled':True},{'enabled':True,'consent':True}):
            entries,called=rewrite_retrieve(self.index,'NLP',never,**kwargs)
            self.assertFalse(called);self.assertTrue(entries)

    def test_rewrite_question_only_and_terms_not_evidence(self):
        calls=[]
        def chat(messages):calls.append(messages);return '["nanoGPT", "not-in-archive"]'
        entries,called=rewrite_retrieve(self.index,'生成模型',chat,enabled=True,consent=True)
        self.assertTrue(called)
        self.assertEqual(calls,[[{'role':'system','content':PROMPT},{'role':'user','content':'生成模型'}]])
        self.assertTrue(entries)
        self.assertTrue(all('not-in-archive' not in e['body'] for e in entries))

    def test_rewrite_failure_and_malformed_fallback(self):
        def fail(messages):raise TimeoutError()
        for chat in (fail,lambda m:'secret /path',lambda m:'["/private/file"]',lambda m:'{}',lambda m:'[]'):
            before=self.index.retrieve('NLP 问题',lexical_terms('NLP 问题'),limit=60)
            entries,called=rewrite_retrieve(self.index,'NLP 问题',chat,enabled=True,consent=True)
            self.assertTrue(called);self.assertEqual(entries,before)

    def test_rewrite_date_type_filter(self):
        entries,_=rewrite_retrieve(self.index,'生成模型',lambda m:'["nanoGPT"]',
                                   '2026-09-01','2026-09-30',enabled=True,consent=True)
        self.assertTrue(entries);self.assertTrue(all(e['date']>='2026-09-01' for e in entries))
        entries,_=rewrite_retrieve(self.index,'生成模型',lambda m:'["nanoGPT"]',category='gratitude_diary',enabled=True,consent=True)
        self.assertEqual(entries,[])


class EmbeddingExperimentTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.calls=[]
        def encode(text,kind):
            self.calls.append((text,kind))
            return np.array([1.,0.],dtype=np.float32)
        self.index=MemoryIndex(encode);self.diaries=dataset()[0][:3]

    def test_incremental_duplicate_delete_rebuild_identity(self):
        before=json.dumps(self.diaries,sort_keys=True)
        self.index.sync(self.diaries+[self.diaries[0]]);self.assertEqual(len(self.calls),3)
        self.index.sync(self.diaries);self.assertEqual(len(self.calls),3)
        self.index.sync([{**self.diaries[0],'original_text':'changed'},self.diaries[1]])
        self.assertEqual(len(self.calls),4);self.assertNotIn('d3',self.index.cache)
        self.index.cache={};self.index.sync(self.diaries);self.assertEqual(len(self.calls),7)
        self.assertEqual(json.dumps(self.diaries,sort_keys=True),before)

    def test_filter_before_ranking_and_isolated_instances(self):
        import numpy as np
        self.index.sync(self.diaries)
        vector=np.array([1.,0.])
        self.assertEqual(self.index.rank(vector,begin='2026-08-02',end='2026-08-02'),['d2'])
        self.assertEqual(self.index.rank(vector,selected={'d3'}),['d3'])
        self.assertEqual(self.index.rank(vector,selected=set()),[])
        self.assertEqual(self.index.rank(vector,category='gratitude_diary'),[])
        self.assertEqual(MemoryIndex(self.index.encode).rank(vector),[])

    def test_corruption_unavailable_fallback(self):
        import numpy as np
        self.index.sync(self.diaries)
        self.index.cache['d1']=('bad',np.array([float('nan'),0.]))
        self.assertEqual(self.index.safe_rank('x',['fts']),['fts'])
        def fail(*args):raise OSError('missing local model')
        self.index.encode=fail
        self.assertEqual(self.index.safe_rank('x',['fts']),['fts'])

    def test_rrf_deduplicates_and_deterministic(self):
        self.assertEqual(fuse(['b','a','a'],['a','c'])[0],'a')
        self.assertEqual(fuse([],[]),[])


if __name__=='__main__':unittest.main()
