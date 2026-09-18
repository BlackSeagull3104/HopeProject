"""Synthetic portable-media and bounded PDF layout regressions; no private data."""
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote
from unittest.mock import patch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hope_archive import export_markdown as md, export_documents as doc
from hope_archive.media import media_key


class PortableExportTests(unittest.TestCase):
    def test_documented_direct_script_entrypoint(self):
        source=self.root/'input.json'
        source.write_text(json.dumps({'diaries':[self.diary(self.urls[:1])]}),encoding='utf-8')
        (self.archive/'media_manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        result=subprocess.run([sys.executable,'-B',md.__file__,'--input',str(source),'--archive',str(self.archive),'--output-dir',str(self.out)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['generated'],1)
        path,=self.out.rglob('*.md')
        self.assertEqual(len(self.refs(path)),1)
        self.assertTrue(self.refs(path)[0].is_file())

    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.archive=self.root/'内部归档'
        self.manifest={'media':{}};self.urls=[]
        for index,size in enumerate(((800,450),(600,600),(400,800),(200,1800))):
            path=self.archive/str(index)/'同名图片.png';path.parent.mkdir(parents=True)
            im=Image.new('RGB',size,('#e5eff4','#eadfce','#e4ece0','#efe7ef')[index]);draw=ImageDraw.Draw(im)
            for y in range(20,size[1]-10,36):
                draw.text((15,y),f'Synthetic image {index+1} / line {y//36+1}',fill='#263544')
                draw.line((15,y+19,size[0]-15,y+19),fill='#b6c4ce')
            im.save(path);url=f'https://fixture.invalid/{index}'
            self.urls.append(url);self.manifest['media'][media_key(url)]={'status':'downloaded','local_path':path.relative_to(self.archive).as_posix()}
        self.out=self.root/'中文导出'/'diaries'

    def diary(self,urls,identity=1,text='中文日记 English text'):
        return {'id':identity,'note_date':'2026-09-18','title':'示例标题 / Example',
                'content':[{'text':text},{'kind':'image','media':[{'url':u} for u in urls]}],
                'comments':[{'items':[{'id':'comment','from_name':'示例作者','text':'这是一条留言。 Comment.'}]}]}

    def refs(self,path):
        return [(path.parent/unquote(ref)).resolve() for ref in re.findall(r'<img src="([^"]+)"',path.read_text(encoding='utf-8'))]

    def export(self,diaries):
        result=md.export_diaries({'diaries':diaries},self.manifest,self.archive,self.out)
        self.assertEqual(result['failed'],0)
        return [self.out/md.diary_path(d) for d in diaries]

    def test_single_diary_one_image_exact_original_bytes(self):
        path,=self.export([self.diary(self.urls[:1])]);refs=self.refs(path)
        self.assertEqual(len(refs),1)
        self.assertEqual(refs[0].read_bytes(),(self.archive/'0/同名图片.png').read_bytes())
        self.assertTrue(refs[0].is_relative_to(self.out.resolve()))

    def test_multiple_images_order_and_duplicate_filenames(self):
        path,=self.export([self.diary(self.urls)])
        refs=self.refs(path);self.assertEqual(len(set(refs)),4)
        for index,ref in enumerate(refs):
            self.assertEqual(ref.read_bytes(),(self.archive/str(index)/'同名图片.png').read_bytes())
            self.assertEqual(ref.stem,hashlib.sha256(ref.read_bytes()).hexdigest())

    def test_multiple_diaries_share_asset_and_chinese_tree_can_move(self):
        paths=self.export([self.diary(self.urls[:2],1),self.diary(self.urls[:1],2)])
        self.assertEqual(self.refs(paths[0])[0],self.refs(paths[1])[0])
        self.assertEqual(len(list((self.out/'assets').iterdir())),2)
        moved=self.root/'搬迁之后'/'diaries';moved.parent.mkdir()
        shutil.move(str(self.out),str(moved))
        shutil.rmtree(self.archive)  # Only the isolated TemporaryDirectory fixture.
        for path in moved.rglob('*.md'):
            for ref in self.refs(path):self.assertTrue(ref.is_file());self.assertTrue(ref.is_relative_to(moved))
            text=path.read_text(encoding='utf-8');self.assertNotIn(str(self.root),text)
            self.assertNotIn('https://fixture.invalid',text)

    def test_combined_export_can_move(self):
        result=doc.export_range({'diaries':[self.diary(self.urls[:2])]},self.manifest,self.archive,self.out,'markdown','测试','2026-09-18','2026-09-18')
        self.assertEqual(result['generated'],1)
        moved=self.root/'moved';shutil.move(str(self.out),str(moved));shutil.rmtree(self.archive)
        for path in moved.glob('*.md'):
            self.assertEqual(len(self.refs(path)),2)
            self.assertTrue(all(p.is_file() and p.is_relative_to(moved) for p in self.refs(path)))

    def test_missing_media_does_not_crash(self):
        path,=self.export([self.diary([*self.urls[:1],'https://fixture.invalid/missing'])])
        self.assertIn('Media unavailable locally',path.read_text(encoding='utf-8'))
        self.assertEqual(len(self.refs(path)),1)
        items=list(doc.blocks(self.diary(['https://fixture.invalid/missing']),self.manifest,self.archive))
        self.assertIn(('missing','[本地媒体不可用]'),items)
        self.assertTrue(doc.render_pdf(items).startswith(b'%PDF'))

    def test_unavailable_copy_collision_fails_without_overwriting(self):
        data=(self.archive/'0/同名图片.png').read_bytes();target=self.out/'assets'/(hashlib.sha256(data).hexdigest()+'.png')
        target.parent.mkdir(parents=True);target.write_bytes(b'conflicting fixture')
        result=md.export_diaries({'diaries':[self.diary(self.urls[:1])]},self.manifest,self.archive,self.out)
        self.assertEqual(result['failed'],1);self.assertEqual(target.read_bytes(),b'conflicting fixture')

    def test_shared_semantics_including_title_comments_secondary_and_legacy_media(self):
        diary=self.diary(self.urls[:1]);diary['original_text_secondary']='第二段 secondary'
        diary['legacy_media']={'audio_url':'https://fixture.invalid/missing'}
        plain=list(doc.blocks(diary,self.manifest,self.archive));text=md.render_diary(diary,self.manifest,self.archive,self.out/'test.md')
        for expected in ('示例标题','第二段 secondary','留言','中文日记'):
            self.assertIn(expected,text);self.assertTrue(any(expected in str(v) for k,v in plain if k!='image'))
        self.assertNotIn('diary_id',text)

    def test_pdf_layout_rules_preserve_ratio_order_and_bounds(self):
        sizes=[(800,450),(600,600),(400,800),(200,1800),(40,20),(800,450),(800,450),(800,450)]
        rows=doc.pdf_image_rows([(str(i).encode(),s) for i,s in enumerate(sizes)])
        self.assertEqual([len(r) for r in rows],[2,1,1,1,2,1])
        flattened=[x for r in rows for x in r]
        self.assertEqual([x[0] for x in flattened],[str(i).encode() for i in range(len(sizes))])
        for (_, (w,h)),(ow,oh) in zip(flattened,sizes):
            self.assertAlmostEqual(w/h,ow/oh);self.assertLessEqual(w,doc.PDF_BODY_WIDTH)
            self.assertLessEqual(h,300);self.assertLessEqual(w,ow*.75)
        self.assertLessEqual(flattened[3][1][1],260)
        for row in rows:self.assertLessEqual(sum(s[0] for _,s in row)+doc.PDF_IMAGE_GAP*(len(row)-1),doc.PDF_BODY_WIDTH)

    def test_ten_pdf_visual_fixtures(self):
        cases=[('text-only',[],'Plain English diary.'),('chinese',[],'中文段落。阅读与散步。'),
               ('mixed',[],'中文 English mixed text.'),('landscape',[0],'Landscape image'),
               ('portrait',[2],'Portrait image'),('long',[3],'Long screenshot'),('pair',[0,1],'Two compatible images'),
               ('multiple',[0,1,0,1,2,3],'Multiple images'),('comments',[0],'Image and comments'),
               ('missing',[-1],'Missing media')]
        output=Path(os.environ.get('HOPE_EXPORT_QA_OUTPUT',str(self.root/'pdf-fixtures')));output.mkdir(parents=True,exist_ok=True)
        from reportlab.platypus import Image as PDFImage
        for name,indices,text in cases:
            with self.subTest(name=name):
                urls=[self.urls[i] if i>=0 else 'https://fixture.invalid/missing' for i in indices]
                items=list(doc.blocks(self.diary(urls,text=text),self.manifest,self.archive))
                with patch('reportlab.platypus.Image',wraps=PDFImage) as image:
                    data=doc.render_pdf(items)
                    for call in image.call_args_list:
                        self.assertLessEqual(call.kwargs['width'],doc.PDF_BODY_WIDTH)
                        self.assertLessEqual(call.kwargs['height'],300)
                self.assertTrue(data.startswith(b'%PDF-'));self.assertIn(b'/FontFile2',data)
                (output/(name+'.pdf')).write_bytes(data)
