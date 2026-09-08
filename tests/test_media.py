import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.media import discover_media, localize, local_name


def document(url):
    return {'diaries': [{'id': 1, 'content': [{'kind': 'image', 'media': [{'url': url}, {'url': url}]}], 'legacy_media': {}}]}


class MediaTests(unittest.TestCase):
    def test_discovery_and_names(self):
        doc = document('https://example.test/中文.jpeg')
        doc['diaries'][0]['legacy_media'] = {'audio_url': 'https://example.test/a.mp3', 'video_url': 'https://example.test/a.mp4'}
        self.assertEqual(len(discover_media(doc)), 4)
        name = local_name('https://example.test/中文.jpeg')
        self.assertEqual(name, local_name('https://example.test/中文.jpeg'))
        self.assertRegex(name, r'^[0-9a-f]{64}\.jpeg$')
        self.assertNotEqual(name, local_name('https://other.test/中文.jpeg'))

    @patch('hope_archive.media.urlopen')
    def test_duplicate_skip_manifest_and_collision(self, get):
        response = io.BytesIO(b'original bytes'); response.headers = {}
        get.return_value = response
        with tempfile.TemporaryDirectory() as root:
            doc = document('https://example.test/a.jpeg')
            self.assertEqual(localize(doc, root)['downloaded'], 1)
            self.assertEqual(localize(doc, root)['skipped'], 1)
            self.assertEqual(get.call_count, 1)
            manifest = json.loads((Path(root)/'media_manifest.json').read_text())
            path = Path(root)/next(iter(manifest['media'].values()))['local_path']
            path.write_bytes(b'changed')
            self.assertEqual(localize(doc, root)['failed'], 1)
            self.assertEqual(path.read_bytes(), b'changed')

    @patch('hope_archive.media.urlopen')
    def test_failures(self, get):
        for error in [TimeoutError('timeout'), HTTPError('https://example.test', 404, 'missing', {}, None)]:
            with tempfile.TemporaryDirectory() as root:
                get.side_effect = error
                self.assertEqual(localize(document('https://example.test/a'), root)['failed'], 1)
        get.side_effect = None
        response = io.BytesIO(b''); response.headers = {}; get.return_value = response
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(localize(document('https://example.test/a'), root)['failed'], 1)
            self.assertEqual(localize(document('file:///bad'), root)['failed'], 1)


if __name__ == '__main__': unittest.main()
