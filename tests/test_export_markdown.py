from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.export_markdown import diary_path, render_diary, export_diaries
from hope_archive.media import media_key


class MarkdownTests(unittest.TestCase):
    def test_text_null_filename_and_utf8(self):
        diary = {'id': 12, 'note_date': None, 'original_text': '  中文\n\n😀  '}
        path = diary_path(diary)
        self.assertEqual(path, Path('unknown/unknown_12.md'))
        text = render_diary(diary, {}, Path('.'), path)
        self.assertIn(diary['original_text'], text)
        diary['original_text'] = 'changed'
        self.assertEqual(path, diary_path(diary))
        diary['id'] = '../<>中文'
        self.assertNotIn('..', str(diary_path(diary)))

    def test_order_multiple_images_relative_and_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); (root/'media').mkdir(); (root/'media/a.jpg').write_bytes(b'a')
            url = 'https://example.test/a.jpg'
            manifest = {'media': {media_key(url): {'status': 'downloaded', 'local_path': 'media/a.jpg'}}}
            diary = {'id': 1, 'note_date': '2026-09-08', 'content': [
                {'text': 'AAA'}, {'kind': 'image', 'media': [{'url': url}, {'url': 'https://example.test/missing'}]}, {'text': 'BBB'}]}
            text = render_diary(diary, manifest, root, root/diary_path(diary))
            self.assertIn('![](../../media/a.jpg)', text)
            self.assertLess(text.index('AAA'), text.index('![]'))
            self.assertLess(text.index('![]'), text.index('BBB'))
            self.assertIn('Media unavailable locally', text)
            self.assertNotIn('![](https:', text)

    def test_comments_and_original_source(self):
        diary = {'id': 1, 'original_text': 'source\n', 'content': [{'text': 'block'}],
                 'comments': [{'bundle_id': 'g', 'items': [{'id': 2, 'from_name': '名字', 'created_at': 123,
                                                         'reply_to_id': 1, 'text': '  评论😀\n'}]}]}
        text = render_diary(diary, {}, Path('.'), diary_path(diary))
        for expected in ['source\n', 'block', '名字', 'Reply to: 1', '  评论😀\n', '123']:
            self.assertIn(expected, text)

    def test_existing_output_and_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            doc = {'diaries': [{'id': 1, 'original_text': 'original'}]}
            self.assertEqual(export_diaries(doc, {}, root)['generated'], 1)
            self.assertEqual(export_diaries(doc, {}, root)['skipped'], 1)
            doc['diaries'][0]['original_text'] = 'changed'
            self.assertEqual(export_diaries(doc, {}, root)['failed'], 1)
            self.assertIn('original', (Path(root)/diary_path(doc['diaries'][0])).read_text())


if __name__ == '__main__': unittest.main()
