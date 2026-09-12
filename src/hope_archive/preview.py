"""Online diary preview: existing request/normalization, no filesystem writes."""
from . import api, application
from .diary_types import filter_value
from .normalization import normalize_diaries
from .export_markdown import display_value, EMOTION_LABELS, WEATHER_LABELS


class PreviewError(Exception):
    pass


def for_date(user_id, selected, category='all'):
    application.validate_date_range(selected, selected)
    request_filter = filter_value(category)
    try:
        entries = api.fetch_all_diaries(user_id, selected, selected, note_type=request_filter,
                                        data_dir=None, max_pages=50, timeout=20)
        document = normalize_diaries(entries)
        for diary in document['diaries']:
            owner = diary['author'].get('id')
            if owner is not None and str(owner) != user_id:
                raise PreviewError('预览响应与当前账号不符。')
            if (diary.get('note_date') or '')[:10] != selected:
                raise PreviewError('预览响应日期不符，请稍后重试。')
            diary['emotion_label'] = display_value(diary['emotion'], EMOTION_LABELS)
            diary['weather_label'] = display_value(diary['weather'], WEATHER_LABELS)
        return dict(document, date=selected, capsulePreview='pending')
    except api.DiaryAPIError:
        raise PreviewError('日记预览请求失败，请检查网络或稍后重试。') from None
    except (ValueError, TypeError, AttributeError):
        raise PreviewError('日记预览响应格式无效，请稍后重试。') from None


def media_references(document):
    from urllib.parse import urlsplit
    import secrets
    refs = {}
    for diary in document['diaries']:
        if not any(b.get('text') or b.get('media') for b in diary['content']) and diary.get('original_text'):
            diary['content'].insert(0, {'kind': 'text', 'text': diary['original_text'], 'media': []})
        media = [m for b in diary['content'] for m in b['media']]
        for field, kind in [('audio_url', 'audio'), ('video_url', 'video')]:
            url = diary['legacy_media'].get(field)
            if url:
                diary['content'].append({'kind': kind, 'text': None, 'media': [{'url': url}]})
                media.append(diary['content'][-1]['media'][0])
        diary['legacy_media'] = {}
        for item in media:
            url = item.pop('url', None)
            item.pop('file_id', None)
            try:
                parts = urlsplit(url) if isinstance(url, str) else None
                valid = parts and parts.scheme == 'https' and parts.hostname and not parts.username and not parts.password
            except ValueError:
                valid = False
            if valid and len(refs) < 200:
                key = secrets.token_urlsafe(16)
                refs[key] = url
                item['key'] = key
    return refs


def load_media(url):
    import base64
    import ipaddress
    import socket
    from urllib.parse import urlsplit
    from urllib.request import Request, build_opener
    from .auth import _NoAuthRedirect
    try:
        parts = urlsplit(url)
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('Nonpublic media host')
        with build_opener(_NoAuthRedirect()).open(Request(url), timeout=20) as response:
            mime = response.headers.get_content_type()
            if mime not in ('image/png', 'image/jpeg', 'image/webp', 'image/gif', 'video/mp4', 'audio/mpeg', 'audio/mp4', 'audio/ogg', 'audio/wav'):
                raise ValueError('Unsupported media')
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError('Preview limit')
        return {'source': 'data:' + mime + ';base64,' + base64.b64encode(body).decode('ascii')}
    except (OSError, ValueError):
        raise PreviewError('媒体暂时无法预览，或超过 8 MB；可通过下载归档保存后查看。') from None
