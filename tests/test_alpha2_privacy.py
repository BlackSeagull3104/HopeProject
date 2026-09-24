"""Synthetic metadata canaries: no real account/archive/credential fixtures."""
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from hope_archive import api, application, privacy
from hope_archive.normalization import normalize_diaries
from hope_archive.library import Library
from hope_archive.search import SearchIndex
from hope_archive.ai_assistant import DiaryAssistant
from hope_archive.settings import Settings
from test_ai_assistant import FakeSettings


class PrivacyTests(unittest.TestCase):
    def entry(self):
        private = dict(phone='META-CANARY', qq='META-CANARY', email='META-CANARY',
                       token='META-CANARY', address='META-CANARY', deviceId='META-CANARY')
        return dict(dairyId='synthetic', noteDate='2024-01-01', noteType=1,
                    dairy='NLP 作者主动写下 13800000000，保留正文。',
                    user=dict(id='synthetic-user', nickName='合成作者', **private),
                    commentList=[dict(bundleId='group', detail=[dict(commentId='reply',
                        comments='评论正文 10001', fromUser=dict(id='other', nickName='合成评论者', **private),
                        **private)])], **private)

    def test_every_persisted_boundary_and_ai_context(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = dict(status=1, datas=dict(total=1, list=[self.entry()]), session='META-CANARY')
            with patch.object(api, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                entries = api.fetch_all_diaries('synthetic-user', '2024-01-01', '2024-01-01', data_dir=root)
            document = normalize_diaries(entries)
            source = root/'processed/diaries.normalized.json'
            source.write_text(json.dumps(document), encoding='utf-8')
            for file in root.rglob('*.json'):
                self.assertNotIn('META-CANARY', file.read_text(encoding='utf-8'))
            self.assertIn('13800000000', json.dumps(document))
            self.assertIn('10001', json.dumps(document))
            library = Library(root, root)
            self.assertNotIn('META-CANARY', json.dumps(library.browse({}, 'synthetic-user')))
            exported = library.export(dict(beginDate='2024-01-01', endDate='2024-01-01', format='markdown'), root/'archive', 'synthetic-user')
            self.assertNotIn('META-CANARY', Path(exported['path']).read_text(encoding='utf-8'))
            index = SearchIndex(root, root/'cache')
            settings = FakeSettings()
            result = DiaryAssistant(index, settings).ask(dict(question='NLP', provider='mock', disclosureAccepted=True))
            self.assertTrue(result['providerCalled'])
            self.assertNotIn('META-CANARY', json.dumps(settings.calls))
            self.assertNotIn(str(root), json.dumps(settings.calls))
            self.assertEqual(index.query('META-CANARY')['items'], [])

    def test_nested_metadata_in_scalar_fields_is_not_copied(self):
        entry = self.entry()
        entry['commentList'][0]['detail'][0]['tag'] = {'phone': 'META-CANARY'}
        entry['user']['nickName'] = {'token': 'META-CANARY'}
        self.assertNotIn('META-CANARY', json.dumps(normalize_diaries([entry])))

    def test_capsule_list_and_detail_are_minimized(self):
        entry = dict(id='c1', hopeInfo='主动记录 13800000000', user=dict(id='u', phone='META-CANARY'), token='META-CANARY')
        for data in (entry, dict(totalCount=1, datas=[entry])):
            result = privacy.minimized_response(json.dumps(dict(status=1, datas=data)).encode(), 'capsule')
            self.assertNotIn('META-CANARY', json.dumps(result))
            self.assertIn('13800000000', json.dumps(result))

    def test_errors_never_write_provider_or_exception_payload(self):
        for payload in (b'META-CANARY', b'{"status":0,"message":"META-CANARY"}'):
            self.assertNotIn('META-CANARY', json.dumps(privacy.minimized_response(payload)))
        with TemporaryDirectory() as tmp, patch.object(application, 'fetch_all_diaries', side_effect=RuntimeError('META-CANARY')):
            with self.assertRaises(application.ArchiveError):
                application.export_archive('synthetic', '2024-01-01', '2024-01-01', 0, tmp)
            for log in Path(tmp).rglob('*.log'):
                self.assertNotIn('META-CANARY', log.read_text(encoding='utf-8'))

    def test_folder_open_uses_known_directory_without_shell(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(Path(tmp)/'profile')
            with patch('hope_archive.settings.os.startfile', create=True) as opened:
                with self.assertRaises(ValueError): settings.open_archive('diaries')
                settings.save(str(Path(tmp)/'output & 合成'))
                destination = settings.destination('diaries')
                self.assertEqual(settings.open_archive('diaries'), {'opened': True})
                opened.assert_called_once_with(str(destination.resolve()), 'explore')
                for area in ('../', 'cmd.exe', str(Path(tmp)), ''):
                    with self.assertRaises(ValueError): settings.open_archive(area)
                with self.assertRaises(ValueError): settings.open_archive('ai')

    def test_folder_open_rejects_symlink_escape(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = Settings(root/'profile'); settings.save(str(root/'output'))
            try: (root/'output/archive').symlink_to(root, target_is_directory=True)
            except OSError: self.skipTest('OS does not permit synthetic symlink creation')
            with patch('hope_archive.settings.os.startfile', create=True) as opened:
                with self.assertRaises(ValueError): settings.open_archive('diaries')
                opened.assert_not_called()
