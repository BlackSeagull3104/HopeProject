"""Offline presentation tests: synthetic images and diaries only."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.export_markdown import diary_path, render_diary, export_diaries, image_group, image_size, is_long_image, single_image_width
from hope_archive.media import media_key


class MarkdownTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {'media': {}}

    def image(self, name='a.png', size=(200, 400)):
        path = self.root/'media'/name; path.parent.mkdir(exist_ok=True)
        Image.new('RGB', size, 'white').save(path)
        url = 'https://fixture.invalid/' + name
        self.manifest['media'][media_key(url)] = {'status': 'downloaded', 'local_path': 'media/' + name}
        return {'url': url}

    def render(self, diary):
        return render_diary(diary, self.manifest, self.root, self.root/diary_path(diary))

    def test_confirmed_and_unknown_mappings(self):
        diary = {'id': 1, 'emotion': {'value': 1, 'identity': 'emotion_ha'}, 'weather': {'identity': 'weather_qing'}}
        text = self.render(diary)
        self.assertIn('情绪：哈', text); self.assertIn('天气：晴', text)
        self.assertNotIn('"value"', text)
        diary['emotion']['identity'] = 'emotion_sang'
        self.assertIn('情绪：emotion_sang', self.render(diary))
        diary['emotion'] = None; diary['weather'] = {}
        self.assertNotIn('情绪：', self.render(diary))

    def test_comments_names_order_no_debug_fields(self):
        diary = {'id': 1, 'comments': [{'bundle_id': 'SECRET_GROUP', 'items': [
            {'id': 98765, 'from_name': 'yu.', 'text': '  一夜\n\n😀  ', 'created_at': 1234567891234},
            {'id': 98766, 'from_name': 'Alice', 'reply_to_id': 98765, 'text': '回复内容'}]}]}
        text = self.render(diary)
        self.assertIn('**yu.**：  一夜\n\n😀  ', text)
        self.assertIn('↳ **Alice** 回复 **yu.**：回复内容', text)
        self.assertLess(text.index('一夜'), text.index('回复内容'))
        for hidden in ['SECRET_GROUP', '98765', '98766', '1234567891234', 'Reply to:', 'Group ', 'Comment ']:
            self.assertNotIn(hidden, text)

    def test_missing_comments_and_external_reply(self):
        diary = {'id': 1, 'comments': [{'items': [{}, {'author': {'name': 'B'}, 'reply_to_id': 88, 'to_name': 'A', 'text': 'x'}, {'reply_to_id': 99, 'text': 'y'}]}]}
        text = self.render(diary)
        self.assertIn('作者未知：', text)
        self.assertIn('↳ **B** 回复 **A**：x', text)
        self.assertIn('回复对象未知', text)
        self.assertNotIn('None', text)

    def test_single_relative_image_dimensions_and_bytes(self):
        media = self.image(); original = (self.root/'media/a.png').read_bytes()
        text = self.render({'id': 1, 'note_date': '2026-09-08', 'content': [{'kind': 'image', 'media': [media]}]})
        self.assertIn('src="../../media/a.png"', text)
        self.assertIn('width:46%', text)
        self.assertIn('max-width:200px', text)
        self.assertNotIn(str(self.root), text)
        self.assertEqual((self.root/'media/a.png').read_bytes(), original)

    def test_two_contiguous_images_across_blocks(self):
        a,b = self.image('a.png'),self.image('b.png')
        text = self.render({'id': 1, 'content': [{'text': 'A'}, {'kind': 'image', 'text': '', 'media': [a]}, {'kind': 'image', 'media': [b]}, {'text': 'B'}]})
        self.assertEqual(text.count('class="image-group"'), 1)
        self.assertEqual(text.count('width:48%'), 2)
        self.assertLess(text.index('a.png'), text.index('b.png'))

    def test_text_and_whitespace_prevent_regrouping(self):
        a,b = self.image('a.png'),self.image('b.png')
        for separator in ['Middle\n\n中文😀', '  \n']:
            diary = {'id': 1, 'content': [{'text': 'FIRST'}, {'kind': 'image', 'media': [a]}, {'text': separator}, {'kind': 'image', 'media': [b]}]}
            text = self.render(diary)
            self.assertEqual(text.count('class="image-group"'), 2)
            start=text.index('a.png'); middle=text.index(separator,start)
            self.assertLess(start,middle);self.assertLess(middle,text.index('b.png'))

    def test_group_rows(self):
        urls = [self.image(f'{i}.png')['url'] for i in range(5)]
        for count,rows in [(3,1),(4,2),(5,3)]:
            html=image_group(urls[:count],self.manifest,self.root,self.root/'x.md')
            self.assertEqual(html.count('class="image-row"'),rows)
            self.assertEqual(html.count('<img '),count)
            self.assertEqual(html.count('width:31%' if count == 3 else 'width:48%'), count)
            if count == 4:
                rows = html.split('class="image-row"')[1:]
                self.assertEqual([row.count('<img ') for row in rows], [2, 2])

    def test_tiny_landscape_and_unknown_dimensions(self):
        small=self.image('tiny.png',(40,20))
        html=image_group([small['url']],self.manifest,self.root,self.root/'x.md')
        self.assertIn('width:65%',html);self.assertIn('max-width:40px',html)
        (self.root/'bad.png').write_bytes(b'not an image')
        self.assertIsNone(image_size(self.root/'bad.png'))

    def test_single_shapes_and_ordinary_phone_screenshot(self):
        self.assertFalse(is_long_image(1080, 2400))
        self.assertFalse(is_long_image(1080, 1920))
        self.assertEqual(single_image_width((1080, 2400)), 46)
        self.assertEqual(single_image_width((1600, 900)), 65)
        self.assertEqual(single_image_width((1000, 1000)), 55)
        self.assertEqual(single_image_width((1000, 1100)), 55)
        self.assertEqual(single_image_width(None), 55)
        for name, size, percent in [('phone', (108, 240), 46), ('square', (100, 100), 55)]:
            media = self.image(name + '.png', size)
            html = image_group([media['url']], self.manifest, self.root, self.root/'x.md')
            self.assertIn(f'width:{percent}%', html)

    def test_long_image_threshold_full_image_and_bytes(self):
        self.assertFalse(is_long_image(100, 249))
        self.assertTrue(is_long_image(100, 250))
        self.assertTrue(is_long_image(100, 400))
        self.assertFalse(is_long_image(0, 400))
        media = self.image('long.png', (100, 400))
        path = self.root/'media/long.png'
        before = path.read_bytes()
        html = image_group([media['url']], self.manifest, self.root, self.root/'2026/09/x.md')
        self.assertIn('width:38%', html)
        self.assertIn('src="../../media/long.png"', html)
        self.assertIn('width:auto;height:auto', html)
        self.assertNotIn('overflow:hidden', html)
        self.assertNotIn('object-fit:cover', html)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(image_size(path), (100, 400))

    def test_missing_media_and_other_media_break_groups(self):
        a=self.image()
        diary={'id':1,'content':[{'kind':'image','media':[a]}, {'kind':'video','media':[{'url':'https://fixture.invalid/video'}]}, {'kind':'image','media':[{'url':'https://fixture.invalid/missing'}]}]}
        text=self.render(diary)
        self.assertEqual(text.count('class="image-group"'),2)
        self.assertIn('Media unavailable locally',text)
        self.assertNotIn('src="https:',text)

    def test_body_not_duplicated_and_source_unmodified(self):
        diary={'id':1,'original_text':'different legacy body','content':[{'text':'  原文\n\n😀  '}]}
        before=deepcopy(diary);text=self.render(diary)
        self.assertIn('  原文\n\n😀  ',text)
        self.assertEqual(text.count('原文'),1)
        self.assertNotIn('different legacy body',text)
        self.assertNotIn('Original text',text)
        self.assertEqual(diary,before)
        diary['content']=[{'text':'','media':[]}]
        self.assertIn('different legacy body',self.render(diary))

    def test_export_starts_with_heading_without_front_matter(self):
        media = self.image()
        diary = {
            'id': 123, 'note_date': '2026-09-05 08:43:12',
            'emotion': {'identity': 'emotion_ha'},
            'weather': {'identity': 'weather_qing'},
            'content': [{'text': '  原文\n\nEnglish 😀  '},
                        {'kind': 'image', 'media': [media]}, {'text': '图片之后'}],
            'comments': [{'items': [{'id': 7, 'from_name': '示例作者', 'text': ' 评论\n ' }]}],
        }
        document = {'diaries': [diary]}
        before = deepcopy(document)
        result = export_diaries(document, self.manifest, self.root)
        self.assertEqual(result['generated'], 1)
        relative = diary_path(diary)
        self.assertEqual(relative, Path('2026/09/2026-09-05_123.md'))
        rendered = (self.root / relative).read_text(encoding='utf-8')
        self.assertTrue(rendered.startswith('# 2026-09-05\n\n情绪：哈\n\n天气：晴\n\n'))
        self.assertFalse(rendered.startswith('---'))
        for hidden in ['diary_id:', 'note_date:', '08:43:12']:
            self.assertNotIn(hidden, rendered)
        self.assertIn('  原文\n\nEnglish 😀  ', rendered)
        self.assertIn('src="../../media/a.png"', rendered)
        self.assertIn('**示例作者**： 评论\n ', rendered)
        self.assertLess(rendered.index('原文'), rendered.index('<img'))
        self.assertLess(rendered.index('<img'), rendered.index('图片之后'))
        self.assertEqual(document, before)
        self.assertEqual(diary['note_date'], '2026-09-05 08:43:12')

    def test_metadata_like_body_text_is_not_deleted(self):
        # Remove generated metadata, not matching words written by the diarist.
        body = '---\ndiary_id: an example\nnote_date: original text\n---'
        rendered = self.render({'id': 123, 'note_date': '2026-09-05', 'original_text': body})
        self.assertTrue(rendered.startswith('# 2026-09-05\n\n'))
        self.assertIn(body, rendered)

    def test_filename_stable_and_existing_output(self):
        diary={'id':12,'note_date':None,'original_text':'original'}
        self.assertEqual(diary_path(diary),Path('unknown/unknown_12.md'))
        document={'diaries':[diary]};out=self.root/'reading'
        self.assertEqual(export_diaries(document,{},self.root,out)['generated'],1)
        self.assertEqual(export_diaries(document,{},self.root,out)['skipped'],1)
        diary['original_text']='changed'
        self.assertEqual(export_diaries(document,{},self.root,out)['failed'],1)
        self.assertIn('original',(out/diary_path(diary)).read_text())


if __name__ == '__main__': unittest.main()
