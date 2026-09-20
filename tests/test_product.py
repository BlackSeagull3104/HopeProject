import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import ai, capsules, desktop_api, local_api, ocr
from hope_archive.settings import Settings
from hope_archive.library import Library
from hope_archive.export_documents import export_pages


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = desktop_api.DesktopService(self.root/'profile')
        self.addCleanup(self.service.pool.shutdown)

    def call(self, path, body=None, token=None):
        return self.service.dispatch('POST', path, body or {}, token)

    def fixture(self, user='a', category='gratitude_diary', day='2024-01-01', text='合成测试 diary'):
        library = self.service.library if hasattr(self.service,'library') else Library(self.root/'profile')
        root = library.account_root(user)/'snapshot'
        (root/'processed').mkdir(parents=True,exist_ok=True)
        (root/'archive').mkdir(exist_ok=True)
        entry = {'id':category, 'author':{'id':user}, 'note_date':day, 'diary_type':category,
                 'content':[{'kind':'text','text':text,'media':[]}], 'comments':[]}
        (root/'processed/diaries.normalized.json').write_text(json.dumps({'diaries':[entry]}),encoding='utf-8')
        return library

    def test_first_launch_persist_change_and_cancel_no_implicit_path(self):
        self.assertFalse(self.call('/settings/read')['exportConfigured'])
        with self.assertRaises(local_api.RequestError): self.call('/ocr/export',{'pages':[{'text':'edited'}],'format':'txt'})
        for name in ('one','two'):
            root = self.root/name
            self.call('/settings/save',{'exportRoot':str(root)})
            self.assertEqual(Settings(self.root/'profile').read()['exportRoot'],str(root))
            for area in ('diaries','capsules','ocr'):
                self.assertEqual(Settings(self.root/'profile').destination(area),root/'archive' if area=='diaries' else root/'archive'/area)

    def test_preview_and_export_are_local_and_account_scoped(self):
        self.fixture()
        self.fixture('b',text='second account')
        self.service.sessions['a']={'userId':'a','expires':time.monotonic()+100}
        self.service.sessions['b']={'userId':'b','expires':time.monotonic()+100}
        self.call('/settings/save',{'exportRoot':str(self.root/'exports')})
        with patch('hope_archive.api.urlopen',side_effect=AssertionError('Network forbidden')):
            result=self.service.library.browse({},'a')
            self.assertEqual(len(result['diaries']),1)
            self.assertNotIn('second account',json.dumps(result))
            result=self.call('/library/export',{'beginDate':'2024-01-01','endDate':'2024-01-01','format':'txt'},'a')
            self.assertEqual(Path(result['path']).parent,self.root/'exports/archive')
            self.assertIn('合成测试',Path(result['path']).read_text(encoding='utf-8'))
            self.assertEqual(len(self.service.library.browse({},'b')['diaries']),1)

    def test_all_diary_types_share_destination(self):
        self.call('/settings/save',{'exportRoot':str(self.root/'exports')})
        for category in ('capsule_diary','gratitude_diary','discovery_diary'):
            self.fixture(category=category)
            r=self.call('/library/export',{'beginDate':'2024-01-01','endDate':'2024-01-01','format':'markdown','diaryType':category})
            self.assertEqual(Path(r['path']).parent,self.root/'exports/archive')

    def test_optional_date_search_inclusive(self):
        self.fixture()
        for body, count in [({},1),({'beginDate':'2024-01-01'},1),({'endDate':'2024-01-01'},1),
                            ({'beginDate':'2024-01-02'},0),({'endDate':'2023-12-31'},0),
                            ({'beginDate':'2024-01-01','endDate':'2024-01-01'},1)]:
            self.assertEqual(self.call('/library/search/query',dict(query='合成',**body))['total'],count)

    def test_download_uses_managed_account_root(self):
        self.service.sessions['a']={'userId':'a','expires':time.monotonic()+100}
        self.call('/settings/save',{'exportRoot':str(self.root/'exports')})
        with patch.object(self.service.pool,'submit') as start:
            self.call('/library/download',{'beginDate':'2024-01-01','endDate':'2024-01-01'},'a')
            self.assertEqual(start.call_args.args[-2].root,self.root/'exports/backup')
        with self.assertRaises(local_api.RequestError): self.call('/library/download',{'beginDate':'2024-01-01','endDate':'2024-01-01','outputDir':'arbitrary'},'a')

    def test_opened_capsule_export_and_reject_unopened(self):
        library=self.fixture()
        folder=library.account_root('a')/'snapshot/processed'
        entries=[{'id':'open','status':'opened','content':'已开启合成正文','metadata':{'status':1,'canOpen':False},
            'title':'测试','keywords':None,'created_at':'2024-01-01','scheduled_at':None,'opened_at':None,'updated_at':None,'media':[]},
            {'id':'closed','status':'unopened','content':'must-not-export','metadata':{}}]
        (folder/'capsules.normalized.json').write_text(json.dumps({'capsules':entries}),encoding='utf-8')
        self.assertEqual(len(self.call('/library/capsules')['items']),1)
        self.call('/settings/save',{'exportRoot':str(self.root/'exports')})
        r=self.call('/library/capsules/export',{'format':'txt'})
        self.assertEqual(Path(r['path']).parent,self.root/'exports/archive/capsules')
        self.assertNotIn('must-not-export',Path(r['path']).read_text(encoding='utf-8'))
        with patch.object(capsules,'request_data') as remote:
            with self.assertRaises(capsules.CapsuleError): capsules.fetch_page('a','unopened',0,folder/'unused')
            remote.assert_not_called()

    def test_capsule_background_only_fetches_opened_details(self):
        self.call('/settings/save',{'exportRoot':str(self.root/'exports')})
        self.service.sessions['a']={'userId':'a','expires':time.monotonic()+100}
        opened={'id':'open','user':{'id':'a'},'openStatus':2,'hopeInfo':'opened synthetic body'}
        closed={'id':'closed','user':{'id':'a'},'openStatus':1,'hopeInfo':'not requested'}
        with patch.object(capsules,'request_data',side_effect=[{'datas':[opened,closed],'totalCount':2},opened]) as remote:
            identity=self.call('/library/capsules/update',token='a')['jobId']
            until=time.monotonic()+5
            while self.service.jobs[identity]['state']=='running' and time.monotonic()<until: time.sleep(.02)
            self.assertEqual(self.service.jobs[identity]['state'],'completed')
            self.assertEqual(remote.call_count,2)
            self.assertEqual(remote.call_args_list[0].args[1]['openStatus'],2)
            self.assertEqual(remote.call_args_list[1].args[1],{'hopeId':'open'})
            self.assertEqual(len(self.call('/library/capsules',token='a')['items']),1)

    def test_editable_pages_all_export_formats_and_collisions(self):
        pages=[{'text':'编辑后的中文 English <safe> & text'}, {'text':'第二页'}]
        for format in ('markdown','pdf','docx','tex','txt'):
            first=export_pages(pages,self.root/'exports',format)
            second=export_pages(pages,self.root/'exports',format)
            self.assertNotEqual(first['path'],second['path'])
            path=Path(first['path'])
            self.assertTrue(path.stat().st_size)
            if format=='pdf': self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
            elif format=='docx':
                from docx import Document
                doc=Document(path)
                self.assertIn('编辑后的中文', '\n'.join(p.text for p in doc.paragraphs))
            else: self.assertIn('编辑后的中文',path.read_text(encoding='utf-8'))

    def test_provider_presets_and_discovery_protocols(self):
        self.assertEqual(len(ai.PRESETS),11)
        self.assertNotEqual(ai.PRESETS['openai']['models'][0],'gpt-4.1-mini')
        for name,preset in ai.PRESETS.items():
            config={'provider':name,'baseUrl':preset['baseUrl'] or 'https://example.com/v1','model':'custom-model-id'}
            self.assertEqual(ai.validate_config(config)['model'],'custom-model-id')
        provider=ai.OpenAICompatibleProvider({'provider':'anthropic','model':'claude-sonnet-4-6'},'synthetic-test-key')
        with patch.object(ai,'build_opener') as opener:
            opener.return_value.open.return_value=BytesIO(b'{"data":[{"id":"claude-sonnet-4-6"}]}')
            self.assertEqual(provider.list_models(),['claude-sonnet-4-6'])
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header('X-api-key'),'synthetic-test-key')
            self.assertIsNone(request.data)
            self.assertIsNone(request.get_header('Authorization'))


class ProductionOCRTests(unittest.TestCase):
    def test_cancel_reaps_worker(self):
        import subprocess
        jobs=ocr.OCRJobs()
        with patch.object(ocr,'worker_command',return_value=[getattr(sys,'_base_executable',sys.executable),'-c','import time; time.sleep(60)']):
            identity=jobs.start([{'name':'synthetic.png','data':''}])['jobId']
            until=time.monotonic()+5
            while jobs.jobs[identity]['process'] is None and time.monotonic()<until: time.sleep(.01)
            process=jobs.jobs[identity]['process']
            self.assertIsNotNone(process)
            jobs.cancel(identity)
            until=time.monotonic()+5
            while jobs.status(identity)['state']=='running' and time.monotonic()<until: time.sleep(.01)
            self.assertEqual(jobs.status(identity)['state'],'cancelled')
            self.assertIsNotNone(process.poll())

    def test_single_images_and_jpeg_webp(self):
        import subprocess
        import os
        fixtures=Path(__file__).parent/'fixtures/ocr'
        for name in ('01_chinese_clear.png','02_english_clear.png','03_mixed_technical.png'):
            for format in (('PNG','JPEG','WEBP') if name.startswith('01') else ('PNG',)):
                from PIL import Image
                data=BytesIO()
                with Image.open(fixtures/name) as im: im.save(data,format=format)
                env=dict(os.environ,PYTHONPATH=os.pathsep.join(p for p in sys.path if p))
                result=subprocess.run(ocr.worker_command(),input=json.dumps({'images':[{'name':name,'data':base64.b64encode(data.getvalue()).decode()}]}).encode(),capture_output=True,env=env,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                self.assertEqual(result.returncode,0)
                page=json.loads(result.stdout)['pages'][0]
                self.assertEqual(page['state'],'success')
                self.assertTrue(page['text'].strip())

    def test_real_offline_batch_order_no_text_errors_and_release(self):
        fixtures=Path(__file__).parent/'fixtures/ocr'
        names=['01_chinese_clear.png','02_english_clear.png','03_mixed_technical.png','16_blank.png']
        images=[{'name':name,'data':base64.b64encode((fixtures/name).read_bytes()).decode()} for name in names]
        images += [{'name':'corrupt.png','data':base64.b64encode(b'not an image').decode()}]
        from PIL import Image
        raw=BytesIO(); Image.new('RGB',(20,20),'white').save(raw,format='BMP')
        images += [{'name':'unsupported.bmp','data':base64.b64encode(raw.getvalue()).decode()}]
        jobs=ocr.OCRJobs()
        self.addCleanup(jobs.close)
        with patch.object(ai.OpenAICompatibleProvider,'_request',side_effect=AssertionError('No AI request')):
            identity=jobs.start(images)['jobId']
            until=time.monotonic()+90
            while jobs.status(identity)['state']=='running' and time.monotonic()<until: time.sleep(.05)
            status=jobs.status(identity)
        self.assertEqual(status['state'],'completed',status.get('error'))
        pages=status['result']['pages']
        self.assertEqual([p['name'] for p in pages],[i['name'] for i in images])
        self.assertIn('图书馆',pages[0]['text'])
        self.assertTrue(pages[1]['text'].strip())
        self.assertIn('Python',pages[2]['text'])
        self.assertEqual(pages[3]['state'],'no-text')
        self.assertEqual([p['state'] for p in pages[4:]],['failed','failed'])
        self.assertIsNone(jobs.jobs[identity]['process'])
        self.assertNotIn('rapidocr',sys.modules)
        jobs.cancel(identity)
        self.assertNotIn('result',jobs.status(identity))


if __name__=='__main__': unittest.main()
