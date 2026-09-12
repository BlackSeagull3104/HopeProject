"""CLI adapter regression tests; no real network requests."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import main, application


class CLITests(unittest.TestCase):
    def invoke(self, extra=()):
        args = ['hope-archive', '--user-id', 'fixture-user', '--begin-date',
                '2026-09-01', '--end-date', '2026-09-08', *extra]
        with patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main.main()

    def test_delegates_arguments_without_page_number(self):
        result = application.ArchiveResult(Path('run'), 1,
            dict(downloaded=0, skipped=0, failed=0), dict(generated=1, skipped=0, failed=0))
        with patch.object(application, 'export_archive', return_value=result) as service:
            self.assertEqual(self.invoke(['--output-dir', 'chosen', '--note-type', '0']), 0)
        self.assertEqual(service.call_args.args, ('fixture-user', '2026-09-01', '2026-09-08', 0, Path('chosen')))
        self.assertTrue(callable(service.call_args.kwargs['on_progress']))

    def test_legacy_root_alias_and_partial_exit(self):
        result = application.ArchiveResult(Path('run'), 1,
            dict(downloaded=0, skipped=0, failed=1), dict(generated=1, skipped=0, failed=0))
        with patch.object(application, 'export_archive', return_value=result) as service:
            self.assertEqual(self.invoke(['--data-dir', 'chosen']), 1)
        self.assertEqual(service.call_args.args[-1], Path('chosen'))

    def test_service_error_exit(self):
        with patch.object(application, 'export_archive', side_effect=application.ArchiveError('fixture', Path('run'))):
            self.assertEqual(self.invoke(), 1)

    def test_invalid_note_type_before_service(self):
        with patch.object(application, 'export_archive') as service:
            with self.assertRaises(SystemExit) as caught:
                self.invoke(['--note-type', '99'])
        self.assertEqual(caught.exception.code, 2)
        service.assert_not_called()

    def test_full_cli_pipeline_normalizes_before_media_and_markdown(self):
        entry = {'dairyId': 7, 'noteDate': '2026-09-05 08:43:12', 'dairy': '中文 body\nunchanged'}
        body = json.dumps({'datas': {'total': 1, 'list': [entry]}}).encode('utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            with patch('hope_archive.api.urlopen', return_value=io.BytesIO(body)), \
                 patch('hope_archive.media.urlopen', side_effect=AssertionError('Unexpected network')), \
                 patch.object(application, 'localize', wraps=application.localize) as media, \
                 patch.object(application, 'export_diaries', wraps=application.export_diaries) as markdown:
                self.assertEqual(self.invoke(['--output-dir', temporary]), 0)
            run = next(Path(temporary).iterdir())
            normalized = json.loads((run / 'processed/diaries.normalized.json').read_text(encoding='utf-8'))
            self.assertEqual(normalized['schema_version'], 1)
            self.assertEqual(normalized['source'], 'hope')
            self.assertEqual(media.call_args.args[0], normalized)
            self.assertEqual(markdown.call_args.args[0], normalized)
            self.assertEqual(normalized['diaries'][0]['id'], 7)
            self.assertEqual(normalized['diaries'][0]['note_date'], entry['noteDate'])
            self.assertEqual(json.loads((run / 'processed/diaries.json').read_text(encoding='utf-8')), [entry])
            self.assertEqual((run / 'raw/diaries/page_0001.json').read_bytes(), body)
            text = (run / 'archive/2026/09/2026-09-05_7.md').read_text(encoding='utf-8')
            self.assertTrue(text.startswith('# 2026-09-05\n'))
            self.assertNotIn('diary_id:', text)
            self.assertNotIn('note_date:', text)
            self.assertIn(entry['dairy'], text)


if __name__ == '__main__':
    unittest.main()
