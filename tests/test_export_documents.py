from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import application, export_documents as exports
from hope_archive.media import media_key


class DocumentExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {'media': {}}
        media = []
        for i, size in enumerate([(800, 400), (400, 800), (200, 1400)]):
            path = self.root / f'image-{i}.png'
            Image.new('RGB', size, ('#d9edf7', '#f5ddcd', '#d3e7d0')[i]).save(path)
            url = f'https://fixture.invalid/{i}'
            self.manifest['media'][media_key(url)] = {'status': 'downloaded', 'local_path': path.name}
            media.append({'url': url})
        self.document = {'diaries': [{'id': 7, 'note_date': '2024-01-01',
            'emotion': {'identity': 'emotion_ha'}, 'weather': {'identity': 'weather_qing'},
            'content': [{'text': '合成日记：中文测试 & < > % _ # \\'}, {'kind': 'image', 'media': media}],
            'comments': [{'items': [{'id': 1, 'from_name': '合成作者', 'text': '留言测试'},
                                    {'reply_to_id': 1, 'from_name': '读者', 'text': '回复测试'}]}]}]}

    def test_all_formats_content_paths_and_repeat_protection(self):
        before = deepcopy(self.document)
        for format in exports.ExportFormat:
            with self.subTest(format=format.value):
                target = self.root / format.value
                stats = exports.export_document(self.document, self.manifest, self.root, target, format)
                self.assertEqual(stats['generated'], 1)
                suffix = 'md' if format.value == 'markdown' else format.value
                path = target / f'2024/01/2024-01-01_7.{suffix}'
                self.assertTrue(path.is_file())
                if format.value in ('markdown', 'tex'):
                    text = path.read_text(encoding='utf-8')
                    for expected in ('2024-01-01', '合成日记', '留言测试', '情绪', '天气'):
                        self.assertIn(expected, text)
                    self.assertNotIn(str(self.root), text)
                elif format.value == 'docx':
                    from docx import Document
                    doc = Document(path)
                    text = '\n'.join(p.text for p in doc.paragraphs)
                    self.assertIn('留言测试', text)
                    self.assertGreater(len(doc.inline_shapes), 3)
                    for shape in doc.inline_shapes:
                        self.assertLessEqual(shape.width.pt, 450.01)
                        self.assertLessEqual(shape.height.pt, 600.01)
                else:
                    self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
                    self.assertIn(b'/FontFile2', path.read_bytes())
                repeat = exports.export_document(self.document, self.manifest, self.root, target, format)
                self.assertEqual(repeat['skipped'], 1)
                original = path.read_bytes()
                changed = deepcopy(self.document)
                changed['diaries'][0]['content'][0]['text'] = 'changed fixture'
                self.assertEqual(exports.export_document(changed, self.manifest, self.root, target, format)['failed'], 1)
                self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.document, before)

    def test_image_ratio_long_split_and_tex_escaping(self):
        w, h = exports.fit_image(400, 800)
        self.assertAlmostEqual(w / h, .5)
        parts = list(exports.image_parts(self.root / 'image-2.png'))
        self.assertEqual(sum(size[1] for _, size in parts), 1400)
        self.assertGreater(len(parts), 1)
        escaped = exports.tex_escape(r'\input{bad}&%$#_^~')
        self.assertNotIn(r'\input{bad}', escaped)
        self.assertIn(r'\textbackslash{}', escaped)

    def test_invalid_format_and_file_destination(self):
        with self.assertRaises(ValueError):
            exports.export_document(self.document, {}, self.root, self.root, 'bad')
        target = self.root / 'file'
        target.write_text('fixture')
        self.assertEqual(exports.export_document(self.document, self.manifest, self.root, target, 'docx')['failed'], 1)

    def test_date_boundaries(self):
        with patch('hope_archive.application.date', wraps=date) as clock:
            clock.today.return_value = date(2026, 9, 10)
            for start, end in [('2026-09-01', '2026-09-08'), ('2026-09-01', '2026-09-10'), ('2026-09-10', '2026-09-10')]:
                application.validate_date_range(start, end)
            for start, end in [('2026-09-08', '2026-09-01'), ('2026-09-01', '2026-09-11')]:
                with self.assertRaises(application.ArchiveError):
                    application.validate_date_range(start, end)


if __name__ == '__main__':
    unittest.main()
