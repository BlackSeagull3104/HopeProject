"""Readable Markdown representation; normalized JSON remains authoritative."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hope_archive.media import media_key

PROJECT = Path(__file__).resolve().parents[2]


def diary_path(diary):
    value = diary.get('id')
    if value is None:
        raise ValueError('Missing diary id')
    identifier = str(value)
    if not re.fullmatch(r'[0-9]+', identifier):
        identifier = hashlib.sha256(json.dumps(value).encode()).hexdigest()
    try:
        day = date.fromisoformat((diary.get('note_date') or '')[:10]).isoformat()
        return Path(day[:4]) / day[5:7] / f'{day}_{identifier}.md'
    except (ValueError, TypeError):
        return Path('unknown') / f'unknown_{identifier}.md'


def media_markdown(url, kind, manifest, archive, markdown_path):
    record = manifest.get('media', {}).get(media_key(url), {})
    local = record.get('local_path')
    if local and record.get('status') in ('downloaded', 'skipped'):
        target = (archive / local).resolve()
        if target.is_relative_to(archive.resolve()) and target.is_file():
            relative = quote(Path(os.path.relpath(target, markdown_path.parent)).as_posix(), safe='/.-_')
            return f'![]({relative})' if kind == 'image' else f'[{kind}]({relative})'
    # Failed media stays visible, but never loads a remote image automatically.
    if isinstance(url, str) and urlsplit(url).scheme in ('https', 'http'):
        link = f'[remote media]({quote(url, safe=":/?=&%.-_~")})'
    else:
        link = json.dumps(url, ensure_ascii=False)
    return f'[Media unavailable locally] {link}'


def render_diary(diary, manifest, archive, markdown_path):
    parts = ['---', 'diary_id: ' + json.dumps(diary.get('id'), ensure_ascii=False),
             'note_date: ' + json.dumps(diary.get('note_date'), ensure_ascii=False), '---',
             '\n# ' + ((diary.get('note_date') or 'Unknown date')[:10])]
    for name in ['emotion', 'weather']:
        parts.append(f'{name}: ' + json.dumps(diary.get(name), ensure_ascii=False))
    content = diary.get('content') or []
    for block in content:
        text = block.get('text')
        if text is not None:
            parts.append(text)  # Do not strip, escape, merge or rewrite source text.
        for media in block.get('media') or []:
            parts.append(media_markdown(media.get('url'), block.get('kind', 'unknown'), manifest, archive, markdown_path))
    original = diary.get('original_text')
    if not content:
        if original is not None: parts.append(original)
    elif original is not None and original != ''.join(b.get('text') or '' for b in content):
        parts.extend(['## Original text (dairy source)', original])
    secondary = diary.get('original_text_secondary')
    if secondary is not None:
        parts.extend(['## Secondary original text', secondary])
    for field, kind in [('audio_url', 'audio'), ('video_url', 'video')]:
        url = (diary.get('legacy_media') or {}).get(field)
        if url: parts.append(media_markdown(url, kind, manifest, archive, markdown_path))
    if diary.get('comments'):
        parts.append('## Comments')
    for group in diary.get('comments') or []:
        parts.append('### Group ' + str(group.get('bundle_id')))
        for comment in group.get('items') or []:
            author = comment.get('from_name')
            if author is None: author = (comment.get('author') or {}).get('name')
            parts.extend(['#### Comment ' + str(comment.get('id')),
                          'Author: ' + str(author),
                          'Time (source value): ' + str(comment.get('created_at')),
                          'Reply to: ' + str(comment.get('reply_to_id'))])
            if comment.get('text') is not None: parts.append(comment['text'])
    return '\n\n'.join(parts) + '\n'


def export_diaries(document, manifest, archive):
    archive = Path(archive)
    stats = dict(entries=len(document['diaries']), generated=0, skipped=0, failed=0)
    seen = set()
    for diary in document['diaries']:
        try:
            path = archive / diary_path(diary)
            if path in seen: raise ValueError('Duplicate diary output path')
            seen.add(path)
            text = render_diary(diary, manifest, archive, path)
            encoded = text.encode('utf-8')
            if path.exists():
                if path.read_bytes() != encoded:
                    raise FileExistsError('Existing Markdown differs; refusing overwrite')
                stats['skipped'] += 1
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream: stream.write(encoded)
                stats['generated'] += 1
        except (OSError, ValueError, TypeError) as exc:
            stats['failed'] += 1
            print(f'Markdown failed: {type(exc).__name__}: {exc}')
    return stats


def main():
    parser = argparse.ArgumentParser(description='Export local normalized diaries to Markdown.')
    parser.add_argument('--input', type=Path, default=PROJECT / 'data/processed/diaries.normalized.json')
    parser.add_argument('--archive', type=Path, default=PROJECT / 'data/archive')
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding='utf-8'))
    path = args.archive / 'media_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    stats = export_diaries(document, manifest, args.archive)
    print(json.dumps(stats))
    return 1 if stats['failed'] else 0


if __name__ == '__main__': raise SystemExit(main())
