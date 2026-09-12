"""Independent time-capsule client and local archive. No unlock operations."""
import base64
from enum import Enum
import json
from pathlib import Path
import tempfile
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .storage import save_raw_response
from .media import localize_refs, media_key

BASE = 'https://hope.wantexe.com/services/'
MAX_PREVIEW = 32 * 1024 * 1024


class CapsuleError(Exception):
    pass


class CapsuleStatus(str, Enum):
    UNOPENED = 'unopened'
    OPENED = 'opened'


STATUS_VALUES = {CapsuleStatus.UNOPENED: 1, CapsuleStatus.OPENED: 2}
PAGE_SIZES = {CapsuleStatus.UNOPENED: 4, CapsuleStatus.OPENED: 20}
ORDER_VALUES = {CapsuleStatus.UNOPENED: 1, CapsuleStatus.OPENED: 2}


def request_data(endpoint, params, raw_path):
    request = Request(BASE + endpoint + '?' + urlencode(params), data=b'',
                      headers={'Accept': 'application/json'}, method='POST')
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
    except (HTTPError, URLError, OSError):
        raise CapsuleError('时间胶囊请求失败，请稍后重试。') from None
    save_raw_response(raw_path, raw)
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise CapsuleError('时间胶囊响应格式无效，原始数据已保留。') from None
    if not isinstance(payload, dict) or type(payload.get('status')) is not int or payload['status'] != 1:
        raise CapsuleError('时间胶囊服务未返回成功状态，原始数据已保留。')
    return payload.get('datas')


def identity(entry):
    value = entry.get('id') if isinstance(entry, dict) else None
    if type(value) not in (str, int) or not str(value).strip():
        raise CapsuleError('时间胶囊缺少有效标识。')
    return str(value)


def fetch_page(user_id, status, offset, raw_path):
    status = CapsuleStatus(status)
    if not user_id or type(offset) is not int or offset < 0:
        raise CapsuleError('时间胶囊分页参数无效。')
    data = request_data('hopeService/getHopesV5', {
        'userId': user_id, 'openStatus': STATUS_VALUES[status], 'beginIndex': offset,
        'perPageCount': PAGE_SIZES[status], 'type': 1, 'orderType': ORDER_VALUES[status]}, raw_path)
    if not isinstance(data, dict):
        raise CapsuleError('时间胶囊列表格式无效。')
    entries = data.get('datas', data.get('list'))
    total = data.get('totalCount', data.get('total'))
    if not isinstance(entries, list) or type(total) is not int or total < 0:
        raise CapsuleError('时间胶囊分页信息不完整。')
    ids = [identity(entry) for entry in entries]
    if len(ids) != len(set(ids)) or offset + len(entries) > total or (not entries and offset < total):
        raise CapsuleError('时间胶囊分页不一致，请重新加载。')
    return entries, total


def fetch_detail(capsule_id, raw_path):
    data = request_data('hopeService/getHope', {'hopeId': capsule_id}, raw_path)
    if identity(data) != capsule_id:
        raise CapsuleError('时间胶囊详情标识不一致。')
    return data


def text(value):
    return value if isinstance(value, str) else None


def scalar(value):
    return value if value is None or type(value) in (str, int, float, bool) else None


def normalize(entry, user_id):
    capsule_id = identity(entry)
    known_users = {str(value['id']) for key in ('user', 'user2')
                   if isinstance(value := entry.get(key), dict) and type(value.get('id')) in (str, int)}
    if known_users and user_id not in known_users:
        raise CapsuleError('返回的时间胶囊参与人与当前账号不符，原始响应已保留。')
    recipient = entry.get('user2')
    recipient_id = recipient.get('id') if isinstance(recipient, dict) else None
    raw_status = entry.get('openStatus')
    if entry.get('hopeType') != 1 and recipient_id is not None and str(recipient_id) == user_id:
        raw_status = entry.get('user2OpenStatus')
    status = {1: 'unopened', 2: 'opened'}.get(raw_status, 'unknown') if type(raw_status) is int else 'unknown'
    items = []
    def add(url, kind):
        if not isinstance(url, str) or not url:
            return
        try:
            parsed = urlsplit(url)
        except ValueError:
            return
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return
        if any(m['url'] == url for m in items):
            return
        items.append({'key': media_key(url), 'kind': kind, 'url': url})
    urls = entry.get('mediaUrlList')
    if isinstance(urls, list) and urls:
        for url in urls:
            add(url, 'video' if isinstance(url, str) and '.mp4' in url.lower() else 'image')
    elif entry.get('videoUrl'):
        add(entry.get('videoUrl'), 'video')
    else:
        client = entry.get('clientImg')
        first = entry.get('hopeImgUrl') or (client.get('imageUrl') if isinstance(client, dict) else None)
        for url in (first, entry.get('hopeImgUrl2'), entry.get('hopeImgUrl3')):
            add(url, 'image')
    for field in ('audioUrl', 'tapeUrl'):
        add(entry.get(field), 'audio')
    # Retain returned body locally; presentation separately limits sealed/unknown data.
    return {'id': capsule_id, 'title': text(entry.get('title')),
            'keywords': text(entry.get('keywords')), 'content': text(entry.get('hopeInfo')),
            'status': status, 'created_at': text(entry.get('createDate')),
            'scheduled_at': text(entry.get('openDate')), 'opened_at': text(entry.get('userOpenDate')),
            'updated_at': text(entry.get('updateDate')), 'media': items,
            'metadata': {key: scalar(entry.get(key)) for key in (
                'openStatus', 'user2OpenStatus', 'canOpen', 'status', 'user2Status', 'type', 'hopeType',
                'openDateStatus', 'openLocationStatus', 'daysBeforeSeal', 'tapeDuration', 'tapeStatus')},
            'video_previews': [text(entry.get(key)) for key in ('videoPreviewUrl', 'videoPreviewUrl2', 'videoPreviewUrl3')]}


def present(capsule):
    visible = capsule['status'] == 'opened' and capsule['metadata']['status'] != -1
    return {key: capsule[key] for key in ('id', 'title', 'keywords', 'status', 'created_at', 'scheduled_at', 'opened_at', 'updated_at')} | {
        'content': capsule['content'] if visible else None,
        'content_available': visible,
        'media': [{'key': m['key'], 'kind': m['kind']} for m in capsule['media']] if visible else [],
        'can_open': capsule['metadata']['canOpen'] if type(capsule['metadata']['canOpen']) is bool else None}


class CapsuleArchive:
    """One session-owned snapshot; detail IDs must originate in its own list."""
    def __init__(self, user_id, output_dir):
        root = Path(output_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='hope-capsules-', dir=root))
        self.user_id = user_id
        self.entries = {}
        self.cursors = {}
        self.counter = 0

    def raw_path(self, kind):
        self.counter += 1
        return self.root / 'raw/capsules' / f'{kind}_{self.counter:05d}.json'

    def save(self):
        path = self.root / 'processed/capsules.normalized.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'schema_version': 1, 'source': 'hope',
            'capsules': list(self.entries.values())}, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def list(self, status, offset):
        status = CapsuleStatus(status)
        cursor = self.cursors.get(status)
        if offset != 0 and (not cursor or offset != cursor['offset']):
            raise CapsuleError('请按列表顺序加载下一页。')
        entries, total = fetch_page(self.user_id, status, offset, self.raw_path('list'))
        ids = {identity(e) for e in entries}
        if offset and (cursor['total'] != total or ids & cursor['ids']):
            raise CapsuleError('列表在分页期间发生变化，请重新加载。')
        normalized = [normalize(e, self.user_id) for e in entries]
        for entry in normalized:
            self.entries[entry['id']] = entry
        self.save()
        next_offset = offset + len(entries)
        self.cursors[status] = {'offset': next_offset, 'total': total, 'ids': ids | (cursor['ids'] if offset else set())}
        return {'items': [present(e) for e in normalized], 'nextOffset': next_offset,
                'hasMore': next_offset < total, 'total': total, 'outputDir': str(self.root)}

    def detail(self, capsule_id):
        previous = self.entries.get(capsule_id)
        if previous is None:
            raise CapsuleError('请先从当前账号列表选择时间胶囊。')
        if not present(previous)['content_available']:
            return present(previous)
        entry = normalize(fetch_detail(capsule_id, self.raw_path('detail')), self.user_id)
        self.entries[capsule_id] = entry
        self.save()
        return present(entry)

    def media(self, capsule_id, key):
        entry = self.entries.get(capsule_id)
        if not entry or not present(entry)['content_available']:
            raise CapsuleError('此时间胶囊内容当前不可预览。')
        item = next((m for m in entry['media'] if m['key'] == key), None)
        if not item:
            raise CapsuleError('找不到此媒体。')
        archive = self.root / 'archive'
        stats = localize_refs([{'url': item['url'], 'kind': item['kind']}], archive)
        if stats['failed']:
            raise CapsuleError('媒体保存失败，请稍后重试。')
        manifest = json.loads((archive / 'media_manifest.json').read_text(encoding='utf-8'))
        path = (archive / manifest['media'][key]['local_path']).resolve()
        if not path.is_relative_to(archive.resolve()) or path.stat().st_size > MAX_PREVIEW:
            raise CapsuleError('媒体已保存，超过32MB请在本地归档中打开。')
        mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif',
                '.webp': 'image/webp', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
                '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.webm': 'video/webm'}.get(path.suffix.lower())
        if not mime:
            raise CapsuleError('媒体已保存，此格式请在本地归档中打开。')
        return {'mime': mime, 'data': base64.b64encode(path.read_bytes()).decode('ascii')}
