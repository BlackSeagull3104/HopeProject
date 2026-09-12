import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive import capsules, local_api, api
from hope_archive.diary_types import filter_value, entry_type, normalized_type
from hope_archive.normalization import normalize_diary


def response(data):
    return io.BytesIO(json.dumps({'status': 1, 'datas': data}).encode())


def entry(id='fixture-1', status=2, **extra):
    return {'id': id, 'openStatus': status, 'hopeInfo': '合成正文',
            'user': {'id': 'fixture-user', 'mobile': 'never-copy'}, **extra}


class DiaryCategoryTests(unittest.TestCase):
    def test_filter_and_entry_values_are_separate(self):
        for semantic, raw in [('all', 0), ('capsule_diary', -1), ('gratitude_diary', 1), ('discovery_diary', 2)]:
            self.assertEqual(filter_value(semantic), raw)
            with tempfile.TemporaryDirectory() as root, patch.object(api, 'urlopen', return_value=response({'total': 0, 'list': []})) as network:
                api.fetch_diary_page('fixture-user', '2024-01-01', '2024-01-02', note_type=filter_value(semantic), raw_dir=Path(root))
                payload = json.loads(network.call_args.args[0].data)
                self.assertEqual(payload['noteType'], raw)
                self.assertEqual(payload['type'], 'mine')
        for raw, semantic in [(0, 'capsule_diary'), (1, 'gratitude_diary'), (2, 'discovery_diary'), (-1, 'unknown'), (None, 'unknown'), ([], 'unknown'), (True, 'unknown')]:
            self.assertEqual(entry_type(raw), semantic)
            self.assertEqual(normalize_diary({'dairyId': 1, 'noteType': raw})['diary_type'], semantic)
        self.assertEqual(normalized_type({'metadata': {'note_type': 0}}), 'capsule_diary')
        self.assertEqual(normalized_type({}), 'unknown')
        with self.assertRaises(ValueError): filter_value('unknown')


class CapsuleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = capsules.CapsuleArchive('fixture-user', self.root)
        self.transport = patch.object(capsules, 'urlopen', side_effect=AssertionError('Unexpected network')).start()
        self.addCleanup(patch.stopall)

    def test_list_requests_both_statuses_offset_and_storage(self):
        for status, raw, size, order in [('unopened',1,4,1), ('opened',2,20,2)]:
            self.transport.side_effect = [response({'datas': [entry(status=raw)], 'totalCount': 2}), response({'list': [entry('fixture-2',raw)], 'total':2})]
            page = self.archive.list(status, 0)
            self.assertTrue(page['hasMore']); self.assertEqual(page['nextOffset'], 1)
            page = self.archive.list(status, 1)
            self.assertFalse(page['hasMore'])
            request = self.transport.call_args.args[0]
            self.assertEqual(request.method, 'POST'); self.assertEqual(request.data, b'')
            self.assertTrue(urlsplit(request.full_url).path.endswith('/hopeService/getHopesV5'))
            self.assertEqual(parse_qs(urlsplit(request.full_url).query), {'userId':['fixture-user'], 'openStatus':[str(raw)], 'beginIndex':['1'], 'perPageCount':[str(size)], 'type':['1'], 'orderType':[str(order)]})
        self.assertEqual(len(list((self.archive.root/'raw/capsules').glob('*.json'))), 4)
        doc = json.loads((self.archive.root/'processed/capsules.normalized.json').read_text())
        self.assertIn('capsules', doc); self.assertNotIn('diaries', doc)
        self.assertNotIn('never-copy', json.dumps(doc))

    def test_empty_and_malformed_pages(self):
        self.transport.side_effect = [response({'datas': [], 'totalCount': 0})]
        self.assertEqual(self.archive.list('opened',0)['items'], [])
        for data in [None, {}, {'datas': [], 'totalCount':1}, {'datas':[None], 'totalCount':1}, {'datas':[entry(),entry()], 'totalCount':2}, {'datas':[], 'totalCount':True}]:
            self.transport.side_effect = [response(data)]
            with self.assertRaises(capsules.CapsuleError): self.archive.list('opened',0)

    def test_offset_drift_repeated_page_and_total_change(self):
        self.transport.side_effect = [response({'datas':[entry()], 'totalCount':2})]
        self.archive.list('opened',0)
        for data in [{'datas':[entry()], 'totalCount':2}, {'datas':[entry('fixture-2')], 'totalCount':3}]:
            self.transport.side_effect = [response(data)]
            with self.assertRaises(capsules.CapsuleError): self.archive.list('opened',1)
        with self.assertRaises(capsules.CapsuleError): self.archive.list('opened',10)

    def test_detail_scope_and_unopened_no_network(self):
        with self.assertRaises(capsules.CapsuleError): self.archive.detail('arbitrary')
        self.archive.entries['sealed'] = capsules.normalize(entry('sealed',1), 'fixture-user')
        self.assertIsNone(self.archive.detail('sealed')['content'])
        self.transport.assert_not_called()
        self.archive.entries['fixture-1'] = capsules.normalize(entry(), 'fixture-user')
        self.transport.side_effect = [response(entry())]
        self.assertEqual(self.archive.detail('fixture-1')['content'], '合成正文')
        self.assertEqual(parse_qs(urlsplit(self.transport.call_args.args[0].full_url).query), {'hopeId':['fixture-1']})
        self.transport.side_effect = [response(entry('wrong'))]
        with self.assertRaises(capsules.CapsuleError): self.archive.detail('fixture-1')

    def test_normalization_dates_status_media_and_privacy(self):
        source = entry(createDate='2024-01-01 12:00:00', openDate='2025-01-01 00:00:00', userOpenDate='2025-02-01 12:00:00', updateDate='2025-02-02 12:00:00', canOpen=True, mediaUrlList=['https://fixture.invalid/a.png','https://fixture.invalid/v.mp4', None], audioUrl='https://fixture.invalid/a.mp3', videoPreviewUrl='https://fixture.invalid/p.png')
        normalized = capsules.normalize(source,'fixture-user')
        self.assertEqual(normalized['created_at'], source['createDate'])
        self.assertEqual(normalized['scheduled_at'], source['openDate'])
        self.assertEqual(normalized['opened_at'], source['userOpenDate'])
        self.assertEqual(normalized['updated_at'], source['updateDate'])
        self.assertEqual([m['kind'] for m in normalized['media']], ['image','video','audio'])
        self.assertTrue(capsules.present(normalized)['can_open'])
        self.assertNotIn('https://', json.dumps(capsules.present(normalized)))
        self.assertNotIn('never-copy', json.dumps(normalized))
        for raw in [99, None, {}, True]:
            result = capsules.normalize(entry(status=raw),'fixture-user')
            self.assertEqual(result['status'], 'unknown')
            self.assertIsNone(capsules.present(result)['content'])
        result = capsules.normalize(entry(user2={'id':'fixture-user'},user2OpenStatus=1,hopeType=2),'fixture-user')
        self.assertEqual(result['status'],'unopened')
        cleared = capsules.normalize(entry() | {'status':-1},'fixture-user')
        self.assertFalse(capsules.present(cleared)['content_available'])

    def test_mismatched_owner_and_malformed_media(self):
        with self.assertRaises(capsules.CapsuleError):
            capsules.normalize(entry(user={'id':'different-user'}), 'fixture-user')
        value = capsules.normalize(entry(mediaUrlList=['http://[invalid', 'file:///private', 'https://user:pass@fixture.invalid/a.png', {}]), 'fixture-user')
        self.assertEqual(value['media'], [])

    def test_legacy_media_and_local_download_preview(self):
        normalized = capsules.normalize(entry(hopeImgUrl='https://fixture.invalid/a.png',hopeImgUrl2='https://fixture.invalid/b.png',tapeUrl='https://fixture.invalid/a.mp3'),'fixture-user')
        self.assertEqual(len(normalized['media']),3)
        video = capsules.normalize(entry(videoUrl='https://fixture.invalid/v.mp4',hopeImgUrl='https://fixture.invalid/a.png'),'fixture-user')
        self.assertEqual([m['kind'] for m in video['media']],['video'])
        self.archive.entries['fixture-1'] = normalized
        media_response = io.BytesIO(b'synthetic-image-bytes');media_response.headers = {}
        with patch('hope_archive.media.urlopen',return_value=media_response) as media_network:
            item = normalized['media'][0]
            result = self.archive.media('fixture-1',item['key'])
            self.assertEqual(result['mime'],'image/png')
            self.assertEqual(media_network.call_count,1)
            self.archive.media('fixture-1',item['key'])
            self.assertEqual(media_network.call_count,1)
        self.assertTrue((self.archive.root/'archive/media_manifest.json').exists())
        with self.assertRaises(capsules.CapsuleError): self.archive.media('fixture-1','unknown')

    def test_local_api_is_session_scoped_and_rejects_protocol_fields(self):
        service = local_api.LocalService(); self.addCleanup(lambda: service.pool.shutdown(wait=True))
        service.sessions = {t:{'userId':'fixture-user','expires':time.monotonic()+100} for t in ['a','b']}
        for body in [{'status':'opened','outputDir':str(self.root),'userId':'other'}, {'status':'opened','outputDir':str(self.root),'offset':True}]:
            with self.assertRaises(local_api.RequestError): service.dispatch('POST','/capsules/list',body,'a')
        self.transport.side_effect = [response({'datas':[entry()], 'totalCount':1})]
        service.dispatch('POST','/capsules/list',{'status':'opened','outputDir':str(self.root)},'a')
        with self.assertRaises(local_api.RequestError): service.dispatch('POST','/capsules/detail',{'id':'fixture-1'},'b')
        with self.assertRaises(local_api.RequestError): service.dispatch('POST','/capsules/list',{'status':'opened','outputDir':str(self.root)},'invalid')


if __name__ == '__main__': unittest.main()
