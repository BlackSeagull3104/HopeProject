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
            request = Request(base + '/auth/login/password', data=json.dumps({'mobile': 'fixture-mobile', 'secret': 'fixture-password'}).encode(),
                headers={'X-Hope-Desktop': key, 'Content-Type': 'application/json', 'X-Hope-Client': 'react'})
            try:
                urlopen(request, timeout=5)
                raise AssertionError('Missing config should prevent remote login')
            except HTTPError as exc:
                assert exc.code == 400
                assert 'LOGIN_PROTOCOL_KEY' in json.load(exc)['error']
                exc.close()
            process.stdin.write('shutdown\n'); process.stdin.flush()
            assert process.wait(timeout=10) == 0
            print('PASS: frozen backend startup, HTTP, writable profile, missing-config guard, owner isolation and clean shutdown.')
        finally:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)


if __name__ == '__main__':
    main()
