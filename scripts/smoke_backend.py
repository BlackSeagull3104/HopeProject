"""Launch real frozen backend from a temporary CWD with no repo or real secrets."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    with tempfile.TemporaryDirectory() as folder:
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'SEND_CODE_PROTOCOL_KEY', 'LOGIN_PROTOCOL_KEY')}
        env['HOPE_ARCHIVE_HOME'] = str(Path(folder) / 'profile')
        env['LOCALAPPDATA'] = folder  # Never read the real user's desktop config.
        process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', cwd=folder, env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            key = secrets.token_hex(32)
            process.stdin.write(json.dumps({'key': key}) + '\n')
            process.stdin.flush()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                ready = json.loads(pool.submit(process.stdout.readline).result(timeout=45))
            base = f"http://127.0.0.1:{ready['port']}"
            with urlopen(Request(base + '/health', headers={'X-Hope-Desktop': key}), timeout=5) as response:
                health = json.load(response)
            assert health['status'] == 'ok'
            assert Path(health['defaultOutputDir']) == Path(env['HOPE_ARCHIVE_HOME']) / 'archives'
            try:
                urlopen(base + '/health', timeout=5)
                raise AssertionError('Unauthenticated desktop request accepted')
            except HTTPError as exc:
                assert exc.code == 403
                exc.close()
            # Synthetic-only offline search proves the frozen bundle includes FTS5.
            root = Path(folder) / 'synthetic-archive'
            root.mkdir()
            (root / 'diaries.normalized.json').write_text(json.dumps({'diaries': [
                {'id': 'fixture', 'note_date': '2024-01-02', 'diary_type': 'gratitude_diary',
                 'original_text': 'synthetic searchable diary'}]}), encoding='utf-8')
            headers = {'X-Hope-Desktop': key, 'Content-Type': 'application/json', 'X-Hope-Client': 'react'}
            with urlopen(Request(base + '/search/query', data=json.dumps({'root': str(root), 'query': 'searchable'}).encode(), headers=headers), timeout=10) as response:
                assert json.load(response)['total'] == 1
            with urlopen(Request(base + '/ai/presets', data=b'{}', headers=headers), timeout=5) as response:
                assert len(json.load(response)['presets']) == 5
            # Presets do not read OS credentials or contact any AI provider.
            # Readiness includes validation of both bundled protocol constants.
            # Do not trigger a real SMS or login request during packaging.
            process.stdin.write('shutdown\n'); process.stdin.flush()
            assert process.wait(timeout=10) == 0
            print('PASS: frozen backend startup, HTTP, writable profile, bundled protocol readiness, owner isolation, FTS5 search, AI presets and clean shutdown.')
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    main()
