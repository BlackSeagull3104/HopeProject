"""Readable Markdown representation; normalized JSON remains authoritative."""
import argparse
from datetime import date
from html import escape
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit
from PIL import Image
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hope_archive.media import media_key

PROJECT = Path(__file__).resolve().parents[2]
EMOTION_LABELS = {'emotion_ha': '哈'}
WEATHER_LABELS = {'weather_qing': '晴 ☀️'}
IMAGE_MAX_HEIGHT = 480  # CSS pixels; limits tall screenshots without editing files.
LONG_IMAGE_RATIO = 2.5  # Provisional height/width threshold, not a semantic classifier.


def is_long_image(width, height):
    """Conservative shape check; ordinary 1080x2400 phone screenshots are not long."""
    return width > 0 and height > 0 and height / width >= LONG_IMAGE_RATIO


def single_image_width(size):
    """Percentage cap only. Intrinsic width and max-height still prevent enlargement."""
    if not size:
        return 55
    width, height = size
    if is_long_image(width, height):
        return 38  # Preserve the entire long image; never crop or truncate.
    ratio = width / height
    if ratio < .85:
        return 46
    if ratio > 1.35:
        return 65
    return 55


def display_value(value, labels):
    value = value or {}
    identity = value.get('identity')
    if identity is not None and identity != '':
        return labels.get(identity, str(identity))
    return None  # Numeric enum values alone are not a verified display mapping.


def resolve_media(url, manifest, archive):
    archive = Path(archive).resolve()
    record = manifest.get('media', {}).get(media_key(url), {})
    local = record.get('local_path')
    if local and record.get('status') in ('downloaded', 'skipped'):
        target = (archive / local).resolve()
        if target.is_relative_to(archive) and target.is_file():
            return target
    return None


def local_media(url, manifest, archive, markdown_path):
    target = resolve_media(url, manifest, archive)
    if target:
        relative = quote(Path(os.path.relpath(target, markdown_path.parent)).as_posix(), safe='/.-_')
        return target, relative
    return None


def portable_media(url, manifest, archive, markdown_path, asset_root=None):
    """Copy original bytes; content hashes make collisions and shared media deterministic."""
    source = resolve_media(url, manifest, archive)
    if source is None:
        return None
    try:
        data = source.read_bytes()
    except OSError:
        return None
    suffix = source.suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9]{1,10}', suffix):
        suffix = '.bin'
    assets = Path(asset_root) if asset_root is not None else markdown_path.parent / 'assets'
    target = assets / (hashlib.sha256(data).hexdigest() + suffix)
    from hope_archive.export_documents import write_exclusive
    write_exclusive(target, data)
    relative = quote(Path(os.path.relpath(target, markdown_path.parent)).as_posix(), safe='/.-_')
    return target, relative


def image_size(path):
    try:
        with Image.open(path) as image:
            width, height = image.size
            if image.getexif().get(274) in (5, 6, 7, 8):
                width, height = height, width
            return width, height
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None  # Unsupported/corrupt dimensions: leave intrinsic sizing to the viewer.


def image_group(urls, manifest, archive, markdown_path, asset_root=None):
    columns = 1 if len(urls) == 1 else 3 if len(urls) == 3 else 2
    rendered = []
    for start in range(0, len(urls), columns):
        cells = []
        for url in urls[start:start + columns]:
            local = portable_media(url, manifest, archive, markdown_path, asset_root)
            size = image_size(local[0]) if local else None
            width_percent = 31 if columns == 3 else 48 if columns == 2 else single_image_width(size)
            width_limit = f'max-width:{size[0]}px;' if size else ''
            if local:
                content = f'<img src="{escape(local[1], quote=True)}" alt="" style="max-width:100%;max-height:{IMAGE_MAX_HEIGHT}px;width:auto;height:auto;">'
            else:
                # HTML containers need HTML fallback, not nested Markdown links.
                safe_url = isinstance(url, str) and urlsplit(url).scheme in ('http', 'https')
                content = '[Media unavailable locally]'
                if safe_url:
                    content += f' <a href="{escape(url, quote=True)}">remote media</a>'
            cells.append(f'<div style="width:{width_percent}%;{width_limit}text-align:center;">{content}</div>')
        rendered.append('<div class="image-row" style="display:flex;justify-content:center;align-items:flex-start;gap:2%;margin:0.5em 0;">' + ''.join(cells) + '</div>')
    return '<div class="image-group">\n' + '\n'.join(rendered) + '\n</div>'


def person_name(comment):
    return comment.get('from_name') or (comment.get('author') or {}).get('name')


def name_markdown(name):
    # Names are labels; comment bodies below are never escaped or stripped.
    return re.sub(r'([\\`*_\[\]<>])', r'\\\1', str(name))


def comment_markdown(comment, authors):
    author = person_name(comment)
    heading = f'**{name_markdown(author)}**' if author else '作者未知'
    target_id = comment.get('reply_to_id')
    if target_id is not None:
        target = comment.get('to_name') or authors.get(target_id) or (comment.get('recipient') or {}).get('name')
        heading = '↳ ' + heading + (f' 回复 **{name_markdown(target)}**' if target else '（回复对象未知）')
    text = comment.get('text')
    return heading + '：' + (text if text is not None else '')


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


def media_markdown(url, kind, manifest, archive, markdown_path, asset_root=None):
    local = portable_media(url, manifest, archive, markdown_path, asset_root)
    if local:
        return f'![]({local[1]})' if kind == 'image' else f'[{kind}]({local[1]})'
    return '[Media unavailable locally]'


def render_diary(diary, manifest, archive, markdown_path, asset_root=None):
    from hope_archive.document import diary_blocks
    markdown_path = Path(markdown_path)
    parts, pending_images = [], []
    def flush_images():
        if pending_images:
            parts.append(image_group(pending_images, manifest, archive, markdown_path, asset_root))
            pending_images.clear()
    for kind, value in diary_blocks(diary):
        if kind == 'image':
            pending_images.append(value[1])
            continue
        flush_images()
        if kind == 'heading': parts.append('# ' + value)
        elif kind in ('title', 'subheading'): parts.append('## ' + value)
        elif kind == 'comment': parts.append(comment_markdown(*value))
        elif kind == 'media': parts.append(media_markdown(value[1], value[0], manifest, archive, markdown_path, asset_root))
        else: parts.append(value)
    flush_images()
    return '\n\n'.join(parts) + '\n'


def export_diaries(document, manifest, archive, output_dir=None):
    archive = Path(archive)
    output_dir = Path(output_dir) if output_dir is not None else archive
    stats = dict(entries=len(document['diaries']), generated=0, skipped=0, failed=0)
    seen = set()
    for diary in document['diaries']:
        try:
            path = output_dir / diary_path(diary)
            if path in seen: raise ValueError('Duplicate diary output path')
            seen.add(path)
            text = render_diary(diary, manifest, archive, path, output_dir / "assets")
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
    parser.add_argument('--output-dir', type=Path, help='Portable Markdown directory, including copied media assets')
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding='utf-8'))
    path = args.archive / 'media_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    stats = export_diaries(document, manifest, args.archive, args.output_dir)
    print(json.dumps(stats))
    return 1 if stats['failed'] else 0


if __name__ == '__main__': raise SystemExit(main())
