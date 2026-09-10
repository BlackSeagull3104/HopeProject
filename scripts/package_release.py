"""Package only the reviewed portable runtime and verify the ZIP before release."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v' + json.loads((ROOT / 'frontend/vite-app/src-tauri/tauri.conf.json').read_text())['version'] + '-dev'


def main():
    portable = ROOT / 'dist/windows/Hope Archive'
    sources = {
        'Hope Archive/Hope Archive.exe': portable / 'Hope Archive.exe',
        'Hope Archive/hope-archive-backend.exe': portable / 'hope-archive-backend.exe',
        'Hope Archive/README.txt': ROOT / 'packaging/DISTRIBUTION_README.txt',
    }
    for source in sources.values():
        if not source.is_file():
            raise SystemExit(f'Missing runtime file: {source.name}')
    output = ROOT / f'dist/releases/Hope-Archive-{TAG}-windows-x64.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in sources.items():
            archive.write(source, name)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != set(sources):
            raise SystemExit('ZIP integrity or layout mismatch')
        for name, source in sources.items():
            if hashlib.sha256(archive.read(name)).digest() != hashlib.sha256(source.read_bytes()).digest():
                raise SystemExit(f'ZIP content mismatch: {name}')
            print(f'Verified: {name} ({source.stat().st_size} bytes)')
    print(f'ZIP: {output.name}')
    print(f'SHA256: {hashlib.sha256(output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
