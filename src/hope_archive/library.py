"""Application-managed archive access. No remote calls for browse or export."""
import base64
import hashlib
import json
import mimetypes
from pathlib import Path
from copy import deepcopy
from .diary_types import normalized_type
from .export_documents import blocks, render_items, write_exclusive, ExportFormat
from .export_markdown import render_diary, display_value, EMOTION_LABELS, WEATHER_LABELS


class Library:
    def __init__(self, home):
        self.home = Path(home)
        self.root = self.home / 'archives'
        self.root.mkdir(parents=True, exist_ok=True)

    def account_root(self, user_id):
        path = self.root / hashlib.sha256(str(user_id).encode()).hexdigest()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def diaries(self, user_id=None):
        root = self.root
        latest = {}
        for source in sorted(root.rglob('diaries.normalized.json'), key=lambda p: (p.stat().st_mtime_ns, str(p))):
            if not source.resolve().is_relative_to(root.resolve()): continue
            data = json.loads(source.read_text(encoding='utf-8-sig'))
            archive = source.parent.parent / 'archive'
            for entry in data.get('diaries', []):
                if user_id:
                    owner = (entry.get('author') or {}).get('id')
                    if owner is not None and str(owner) != str(user_id): continue
                    if owner is None and not source.is_relative_to(self.account_root(user_id)): continue
                identity = (str((entry.get('author') or {}).get('id', '')), normalized_type(entry), str(entry.get('id')))
                latest[identity] = (entry, archive)
        return sorted(latest.values(), key=lambda pair: ((pair[0].get('note_date') or ''), str(pair[0].get('id'))), reverse=True)

    def browse(self, body, user_id=None):
        category, day = body.get('diaryType', 'all'), body.get('date', '')
        result = []
        for original, archive in self.diaries(user_id):
            if day and not (original.get('note_date') or '').startswith(day): continue
            if category != 'all' and normalized_type(original) != category: continue
            item = deepcopy(original)
            item['emotion_label'] = display_value(item.get('emotion'), EMOTION_LABELS)
            item['weather_label'] = display_value(item.get('weather'), WEATHER_LABELS)
            manifest_file = archive / 'media_manifest.json'
            manifest = json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {}
            for block in item.get('content') or []:
                for media in block.get('media') or []:
                    from .media import media_key
                    key = media_key(media.get('url', ''))
                    saved = manifest.get('media', {}).get(key, {}).get('local_path')
                    media.clear()
                    if saved:
                        local = (archive / saved).resolve()
                        if local.is_relative_to(archive.resolve()):
                            media['key'] = str(local.relative_to(self.root.resolve()))
            result.append(item)
        return {'diaries': result}

    def media(self, key, user_id=None):
        path = (self.root / key).resolve()
        allowed = self.account_root(user_id).resolve() if user_id else self.root.resolve()
        if not path.is_relative_to(allowed) or not path.is_file() or path.stat().st_size > 32*1024*1024:
            raise ValueError('本地媒体不可用。')
        mime = mimetypes.guess_type(path.name)[0] or ''
        if not mime.startswith(('image/', 'audio/', 'video/')): raise ValueError('不支持的媒体格式。')
        return {'source': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')}

    def export(self, body, output, user_id=None):
        from .application import validate_date_range
        from datetime import datetime
        import uuid
        begin, end = validate_date_range(body['beginDate'], body['endDate'])
        category = body.get('diaryType', 'all')
        entries = [(e,a) for e,a in self.diaries(user_id) if begin.isoformat() <= (e.get('note_date') or '')[:10] <= end.isoformat()
                   and (category == 'all' or normalized_type(e) == category)]
        if not entries: raise ValueError('此范围没有已下载的本地日记，请先归档。')
        format = ExportFormat(body.get('format', 'markdown'))
        suffix = 'md' if format == ExportFormat.MARKDOWN else format.value
        path = Path(output) / f'Hope日记_{begin}--{end}_{datetime.now():%H%M%S}_{uuid.uuid4().hex[:8]}.{suffix}'
        items, markdown = [], []
        for entry, archive in reversed(entries):
            manifest_path = archive/'media_manifest.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
            if format == ExportFormat.MARKDOWN: markdown.append(render_diary(entry, manifest, archive, path))
            else: items.extend(blocks(entry, manifest, archive))
        data = '\n---\n\n'.join(markdown).encode('utf-8') if format == ExportFormat.MARKDOWN else render_items(items, path, format)
        write_exclusive(path, data)
        return {'path': str(path), 'entries': len(entries)}

    def capsules(self, user_id=None):
        root = self.account_root(user_id) if user_id else self.root
        latest = {}
        for source in sorted(root.rglob('capsules.normalized.json'), key=lambda p: p.stat().st_mtime_ns):
            if not source.resolve().is_relative_to(root.resolve()): continue
            for entry in json.loads(source.read_text(encoding='utf-8')).get('capsules', []):
                if entry.get('status') == 'opened' and (entry.get('metadata') or {}).get('status') != -1:
                    latest[str(entry['id'])] = dict(entry, _archive=source.parent.parent/'archive')
        return sorted(latest.values(), key=lambda e: (e.get('created_at') or '', str(e['id'])), reverse=True)

    def browse_capsules(self, user_id=None):
        from .capsules import present
        items=[]
        for entry in self.capsules(user_id):
            item=present(entry)
            archive=entry['_archive']
            source=archive/'media_manifest.json'
            manifest=json.loads(source.read_text(encoding='utf-8')) if source.exists() else {}
            item['media']=[]
            for media in entry.get('media',[]):
                relative=manifest.get('media',{}).get(media['key'],{}).get('local_path')
                if relative:
                    local=(archive/relative).resolve()
                    if local.is_relative_to(archive.resolve()):
                        item['media'].append({'key':str(local.relative_to(self.root.resolve())),'kind':media['kind']})
            items.append(item)
        return {'items':items}

    def export_capsules(self, body, output, user_id=None):
        from datetime import datetime
        import uuid
        entries = self.capsules(user_id)
        if 'ids' in body:
            if not isinstance(body['ids'],list) or any(not isinstance(i,str) for i in body['ids']): raise ValueError('胶囊选择无效。')
            entries = [e for e in entries if str(e['id']) in body['ids']]
        if not entries: raise ValueError('没有可导出的已开启时间胶囊。')
        format=ExportFormat(body.get('format','markdown'))
        suffix='md' if format == ExportFormat.MARKDOWN else format.value
        path=Path(output)/f'时间胶囊_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:8]}.{suffix}'
        items,markdown=[],[]
        for index,entry in enumerate(entries):
            archive=entry['_archive']
            source=archive/'media_manifest.json'
            manifest=json.loads(source.read_text(encoding='utf-8')) if source.exists() else {}
            document={'id':entry['id'],'title':entry.get('title'),'note_date':entry.get('created_at'),
                'content':[{'kind':'text','text':entry.get('content') or '', 'media':[]},
                    *[{'kind':m['kind'],'media':[{'url':m['url']}]} for m in entry.get('media',[])]], 'comments':[]}
            if format == ExportFormat.MARKDOWN: markdown.append(render_diary(document,manifest,archive,path))
            else:
                if index: items.append(('page',''))
                items.extend(blocks(document,manifest,archive))
        data='\n---\n\n'.join(markdown).encode('utf-8') if format==ExportFormat.MARKDOWN else render_items(items,path,format)
        write_exclusive(path,data)
        return {'path':str(path),'pages':len(entries)}
