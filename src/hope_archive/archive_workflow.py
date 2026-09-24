"""Desktop backup + readable archive transaction; the CLI compatibility path is separate."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from datetime import datetime
from . import api, application, media
from .normalization import normalize_diaries
from .diary_types import filter_value, normalized_type
from .export_documents import ExportFormat, blocks, render_items, write_exclusive
from .export_markdown import render_diary


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def migrate_legacy(home, backup):
    """Copy verified legacy files once; never delete originals or replace differing data."""
    legacy = Path(home) / 'archives'
    backup = Path(backup)
    receipt = backup / 'metadata/legacy-migration.json'
    done = json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
    copied = conflicts = 0
    if not legacy.is_dir(): return {'copied': 0, 'conflicts': 0}
    for source in sorted(legacy.rglob('*')):
        if not source.is_file() or not source.resolve().is_relative_to(legacy.resolve()): continue
        relative = source.relative_to(legacy)
        # Only recovery inputs, not old human-facing exports, logs or incomplete files.
        if source.suffix in ('.tmp', '.part', '.log'): continue
        if not (source.name in ('diaries.normalized.json', 'capsules.normalized.json', 'media_manifest.json')
                or 'raw' in relative.parts or 'media' in relative.parts): continue
        key = relative.as_posix()
        if key in done: continue
        target = backup / relative
        payload = source.read_bytes()
        if target.exists() and target.read_bytes() != payload:
            conflicts += 1
            continue
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.migration-' + uuid.uuid4().hex)
            try:
                shutil.copy2(source, temporary)
                if hashlib.sha256(temporary.read_bytes()).digest() != hashlib.sha256(payload).digest():
                    raise OSError('Legacy copy verification failed')
                # Exclusive final creation protects a concurrently appearing destination.
                with target.open('xb') as stream: stream.write(payload)
                shutil.copystat(source, target)
            finally: temporary.unlink(missing_ok=True)
            copied += 1
        done[key] = hashlib.sha256(payload).hexdigest()
        atomic_json(receipt, done)
    return {'copied': copied, 'conflicts': conflicts}


def formats_for(values):
    if not isinstance(values, list) or not values or len(values) > 5:
        raise ValueError('请选择至少一种归档格式。')
    if any(not isinstance(v,str) for v in values): raise ValueError('归档格式无效。')
    selected = {ExportFormat(v) for v in values}
    if selected & {ExportFormat.PDF, ExportFormat.DOCX}: selected.add(ExportFormat.MARKDOWN)
    return [f for f in ExportFormat if f in selected]


def readable(entries, output, formats, begin, end, on_format=None):
    """One stem/Markdown per operation; each format uses the same normalized entries."""
    output = Path(output)
    stem = f'Hope日记_{begin}--{end}_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:8]}'
    result = []
    for format in formats:
        if on_format: on_format(format.value)
        path = output / (stem + ('.md' if format == ExportFormat.MARKDOWN else '.' + format.value))
        items, markdown = [], []
        for entry, archive in entries:
            manifest_path = archive / 'media_manifest.json'
            manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
            if format == ExportFormat.MARKDOWN: markdown.append(render_diary(entry, manifest, archive, path))
            else:
                if items: items.append(('separator', ''))
                items.extend(blocks(entry, manifest, archive))
        data = '\n---\n\n'.join(markdown).encode('utf-8') if format == ExportFormat.MARKDOWN else render_items(items, path, format)
        write_exclusive(path, data)
        result.append(path.name)
    return result


def run(service, identity, body, user_id, library, output):
    stage = '获取日记'
    def progress(label):
        nonlocal stage
        stage = label
        service.update(identity, stage='正在' + label + '…')
    try:
        account = library.account_root(user_id)
        progress('获取日记')
        # Truly temporary transport workspace, always removed, never used by search/UI.
        work = service.preferences.home / 'work'
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='archive-', dir=work) as temporary:
            entries = api.fetch_all_diaries(user_id, body['beginDate'], body['endDate'],
                note_type=filter_value(body.get('diaryType', 'all')), data_dir=Path(temporary))
            document = normalize_diaries(entries)
            for entry in document['diaries']:
                owner = (entry.get('author') or {}).get('id')
                if owner is not None and str(owner) != user_id: raise ValueError('Account mismatch')
                day = (entry.get('note_date') or '')[:10]
                if not body['beginDate'] <= day <= body['endDate']: raise ValueError('Date mismatch')
                if body.get('diaryType','all') != 'all' and normalized_type(entry) != body['diaryType']: raise ValueError('Category mismatch')
            progress('更新备份')
            version = account / 'raw' / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
            version.mkdir(parents=True)
            raw = Path(temporary)/'raw'
            if raw.exists(): shutil.copytree(raw, version/'responses')
            from .privacy import DIARY, project
            atomic_json(version/'diaries.json', project(entries, [DIARY]))
        normalized = account/'normalized/diaries.normalized.json'
        previous = list(library.diaries(user_id))
        merged = {(normalized_type(e), str(e['id'])): e for e,a in reversed(previous)}
        for entry in document['diaries']: merged[(normalized_type(entry),str(entry['id']))] = entry
        # Import original media from older snapshots without replacing verified current files.
        refs = {}
        for entry, old_archive in previous:
            manifest_path = old_archive/'media_manifest.json'
            if old_archive == account or not manifest_path.exists(): continue
            old = json.loads(manifest_path.read_text(encoding='utf-8'))
            for key, record in old.get('media',{}).items():
                local = record.get('local_path')
                if not local: continue
                source = (old_archive/local).resolve()
                if not source.is_relative_to(old_archive.resolve()) or not source.is_file(): continue
                target = account/'media'/media.local_name(record.get('url',''))
                if not target.exists(): write_exclusive(target,source.read_bytes())
                if target.read_bytes() == source.read_bytes():
                    refs[key] = dict(record,local_path='media/'+target.name,sha256=media.file_hash(target),size=target.stat().st_size,status='downloaded')
        manifest_path = account/'media_manifest.json'
        old = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'media':{}}
        atomic_json(manifest_path, {'schema_version':1,'media':dict(refs,**old.get('media',{}))})
        atomic_json(normalized, dict(document,diaries=list(merged.values())))
        progress('下载媒体')
        stats = media.localize(document,account)
        selected = [(e,account) for e in document['diaries']]
        files=[]
        formats=formats_for(body['formats'])
        # readable() uses a shared stem for this batch, including the automatic Markdown.
        progress('生成归档文档')
        if selected: files=readable(selected,output,formats,body['beginDate'],body['endDate'],lambda name:progress('生成 '+name.upper()))
        from .search import SearchIndex
        SearchIndex(library.root,service.search_cache).sync()
        service.update(identity,state='partial' if stats['failed'] else 'completed',
            stage=f'归档完成：{len(selected)} 篇日记，{len(files)} 个文档。'+(' 部分媒体下载失败，可再次归档重试。' if stats['failed'] else ''),
            files=files,diaryCount=len(selected),media=stats)
    except Exception:
        service.update(identity,state='failed',stage=stage+'失败，请检查网络或文件夹权限后重试；已保存备份保留。')
