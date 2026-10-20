"""Create a component ZIP and reviewable pinned catalog; never upload or edit source.

Run only during a separately authorized component release. Review/copy the output
catalog into src/hope_archive/runtime_catalog.py before building the thin app.
"""
import argparse
import hashlib
from pathlib import Path
import pprint
import re
import zipfile


def prepare(source, output, version, url):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', version) or not url.startswith('https://'):
        raise ValueError('Require a safe version and immutable HTTPS asset URL')
    if output.is_relative_to(source): raise ValueError('Output must be outside runtime')
    if not (source / 'hope-archive-ocr.exe').is_file(): raise ValueError('Worker missing')
    from hope_archive.optional_runtime import safe_name
    paths = sorted(p for p in source.rglob('*') if p.is_file())
    files = {}
    for path in paths:
        name = path.relative_to(source).as_posix()
        if not safe_name(name) or path.is_symlink(): raise ValueError('Unsafe component input')
        with path.open('rb') as stream:
            files[name] = dict(bytes=path.stat().st_size, sha256=hashlib.file_digest(stream, 'sha256').hexdigest())
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f'hope-local-runtime-{version}.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for path in paths: bundle.write(path, path.relative_to(source).as_posix())
    with archive.open('rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    catalog = dict(version=version, url=url, bytes=archive.stat().st_size, sha256=digest, files=files)
    (output / 'runtime_catalog.py').write_text(
        '# Reviewed immutable component metadata; no remote manifest execution.\nRUNTIME = ' +
        pprint.pformat(catalog, sort_dicts=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('--version', required=True)
    parser.add_argument('--url', required=True)
    args = parser.parse_args()
    prepare(args.source, args.output, args.version, args.url)
