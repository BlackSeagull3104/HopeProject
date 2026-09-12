"""Application tests use only synthetic inputs and local temporary directories."""
from datetime import date
import inspect
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.application import ArchiveError, export_archive, validate_request


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Unexpected network calls always fail, including media calls.
        self.api = patch('hope_archive.api.urlopen', side_effect=AssertionError('Unexpected network')).start()
        self.media_network = patch('hope_archive.media.urlopen', side_effect=AssertionError('Unexpected network')).start()
        self.addCleanup(patch.stopall)

    def run_export(self, **kwargs):
        return export_archive('fixture-user', '2026-09-01', '2026-09-08', 0, self.root, **kwargs)

    def test_invalid_inputs_before_any_network_or_output(self):
        for user,begin,end,note,root in [('', '2026-09-01','2026-09-08',0,self.root),
            ('x','2026-09-09','2026-09-01',0,self.root), ('x','20260901','2026-09-08',0,self.root),
            ('x','2026-02-30','2026-09-08',0,self.root),('x','2026-09-01','2026-09-08',99,self.root),
            ('x','2026-09-01','2026-09-08',0,'')]:
            with self.assertRaises(ArchiveError): export_archive(user,begin,end,note,root)
        self.api.assert_not_called(); self.assertEqual(list(self.root.iterdir()), [])

    def test_date_rules_before_network_or_output(self):
        with patch('hope_archive.application.date', wraps=date) as clock:
            clock.today.return_value = date(2024, 3, 1)
            for begin, end in [('2024-02-29', '2024-03-01'), ('2024-03-01', '2024-03-01')]:
                self.assertEqual(validate_request('fixture', begin, end, 0, self.root), self.root)
            cases = [
                ('2024-03-02', '2024-03-02', '开始日期不能晚于今天'),
                ('2024-03-01', '2024-03-02', '结束日期不能晚于今天'),
                ('2024-03-01', '2024-02-29', '开始日期不能晚于结束日期'),
                ('2024-02-30', '2024-03-01', '日期无效'),
                ('not-a-date', '2024-03-01', '日期格式'),
            ]
            for begin, end, message in cases:
                with self.subTest(begin=begin, end=end):
                    with self.assertRaisesRegex(ArchiveError, message):
                        export_archive('fixture', begin, end, 0, self.root)
            self.api.assert_not_called()
            self.assertEqual(list(self.root.iterdir()), [])

    def test_output_file_rejected(self):
        path=self.root/'file';path.write_text('keep')
        with self.assertRaisesRegex(ArchiveError,'文件夹'):
            validate_request('x','2026-09-01','2026-09-08',0,path)

    def test_public_api_hides_backend_parameters(self):
        parameters=inspect.signature(export_archive).parameters
        for name in ['page_num','page_size','pageNum','pageSize','type','endpoint','headers']:
            self.assertNotIn(name,parameters)

    def test_real_core_orchestration_with_mock_http_and_mine(self):
        self.api.side_effect = lambda *a, **k: io.BytesIO(json.dumps({'datas':{'total':1,'list':[{'dairyId':7,'dairy':'中文 fixture'}]}}).encode())
        progress=[];result=self.run_export(on_progress=progress.append)
        self.assertTrue(result.complete);self.assertEqual(result.diary_count,1)
        self.assertEqual(result.output_dir.parent,self.root)
        self.assertTrue((result.output_dir/'raw/diaries/page_0001.json').exists())
        self.assertTrue((result.output_dir/'processed/diaries.json').exists())
        self.assertTrue((result.output_dir/'processed/diaries.normalized.json').exists())
        self.assertEqual(len(list((result.output_dir/'archive').rglob('*.md'))),1)
        payload=json.loads(self.api.call_args.args[0].data)
        self.assertEqual(payload['type'],'mine');self.assertEqual(payload['pageNum'],1)
        self.assertEqual(payload['pageSize'],20);self.assertEqual(payload['noteType'],0)
        self.assertEqual(progress[-1],'归档完成')
        second=self.run_export();self.assertNotEqual(result.output_dir,second.output_dir)

    def test_stage_errors_are_clear_and_keep_cause(self):
        with patch('hope_archive.application.fetch_all_diaries',side_effect=RuntimeError('fixture detail')):
            with self.assertRaises(ArchiveError) as caught:self.run_export()
            self.assertIn('获取日记失败',str(caught.exception))
            self.assertNotIn('fixture detail',str(caught.exception))
            self.assertTrue((caught.exception.output_dir/'error.log').exists())
        with patch('hope_archive.application.fetch_all_diaries',return_value=[{'bad':'schema'}]):
            with self.assertRaisesRegex(ArchiveError,'标准化失败'):self.run_export()

    def test_media_failure_returns_partial_result_and_markdown(self):
        entry={'dairyId':1,'dairy':'body','noteInfo2':{'richTextInfo':[{'type':2,'fileList':[{'mediaUrl':'invalid-url'}]}]}}
        with patch('hope_archive.application.fetch_all_diaries',return_value=[entry]):
            result=self.run_export()
        self.assertFalse(result.complete);self.assertEqual(result.media['failed'],1)
        self.assertEqual(result.markdown['generated'],1)
        self.media_network.assert_not_called()

    def test_markdown_failure_is_not_complete(self):
        with patch('hope_archive.application.fetch_all_diaries',return_value=[]), patch('hope_archive.application.export_diaries',return_value={'entries':0,'generated':0,'skipped':0,'failed':1}):
            result=self.run_export()
        self.assertFalse(result.complete)


if __name__ == '__main__':unittest.main()
