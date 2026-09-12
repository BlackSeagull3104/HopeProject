"""Localize normalized media without importing account or downloader code."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PROJECT = Path(__file__).resolve().parents[2]


def discover_media(document):
    refs = []
    for diary in document['diaries']:
        for block in diary.get('content') or []:
            for media in block.get('media') or []:
                refs.append({'diary_id': diary['id'], 'kind': block.get('kind', 'unknown'),
                             'url': media.get('url'), 'file_id': media.get('file_id')})
        for field, kind in [('audio_url', 'audio'), ('video_url', 'video')]:
            url = (diary.get('legacy_media') or {}).get(field)
            if url:
                refs.append({'diary_id': diary['id'], 'kind': kind, 'url': url, 'file_id': None})
    return refs


def media_key(url):
    return hashlib.sha256(json.dumps(url, ensure_ascii=False).encode('utf-8')).hexdigest()


def local_name(url):
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix not in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic', '.mp3', '.wav', '.m4a', '.ogg', '.mp4', '.mov', '.webm'}:
        suffix = '.bin'
    return media_key(url) + suffix


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_manifest(path, manifest):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def localize(document, archive, timeout=30):
    return localize_refs(discover_media(document), archive, timeout)


def localize_refs(refs, archive, timeout=30):
    archive = Path(archive)
    archive.mkdir(parents=True, exist_ok=True)
    manifest_path = archive / 'media_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest = {'schema_version': 1, 'media': dict(previous.get('media', {}))}
    unique = {media_key(r['url']): r for r in refs}
    stats = dict(total_references=len(refs), unique_references=len(unique), downloaded=0, skipped=0, failed=0)
    for key, ref in unique.items():
        url = ref['url']
        record = {'url': url, 'kind': ref['kind'], 'status': 'failed', 'local_path': None}
        temporary = None
        try:
            parsed = urlsplit(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Invalid HTTP(S) media URL')
            relative = 'media/' + local_name(url)
            target = archive / relative
            old = manifest['media'].get(key, {})
            if target.exists():
                if old.get('sha256') != file_hash(target) or not target.stat().st_size or old.get('size') != target.stat().st_size:
                    raise ValueError('Existing file is unverified or changed; refusing overwrite')
                record.update(local_path=relative, sha256=old['sha256'], size=target.stat().st_size, status='skipped')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_suffix(target.suffix + '.part')
                # Exclusive creation also detects unfinished or concurrent runs.
                stream = temporary.open('xb')
                try:
                    with stream, urlopen(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=timeout) as response:
                        size = 0
                        for chunk in iter(lambda: response.read(1024 * 1024), b''):
                            stream.write(chunk)
                            size += len(chunk)
                        length = response.headers.get('Content-Length')
                        if not size or (length is not None and size != int(length)):
                            raise ValueError('Empty or incomplete response body')
                    # Windows rename refuses existing destinations.
                    if target.exists():
                        raise FileExistsError('Destination appeared during download')
                    temporary.rename(target)
                finally:
                    if temporary.exists():
                        temporary.unlink()
                record.update(local_path=relative, sha256=file_hash(target), size=size, status='downloaded')
        except Exception as exc:
            # A media failure is isolated; no diary content is discarded.
            record['error'] = f'{type(exc).__name__}: {exc}'
        manifest['media'][key] = record
        stats[record['status']] += 1
        save_manifest(manifest_path, manifest)
        print(f"Media {list(unique).index(key)+1}/{len(unique)}: {record['status']}", flush=True)
    save_manifest(manifest_path, manifest)
    return stats


def main():
    parser = argparse.ArgumentParser(description='Download normalized media with GET only.')
    parser.add_argument('--input', type=Path, default=PROJECT / 'data/processed/diaries.normalized.json')
    parser.add_argument('--archive', type=Path, default=PROJECT / 'data/archive')
    args = parser.parse_args()
    document = json.loads(args.input.read_text(encoding='utf-8'))
    stats = localize(document, args.archive)
    print(json.dumps(stats))
    return 1 if stats['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
