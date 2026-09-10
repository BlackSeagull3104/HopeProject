"""Packaged desktop adapter; existing development API and Hope core stay unchanged."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import threading

from . import auth, local_api


def user_home():
    override = os.environ.get('HOPE_ARCHIVE_HOME')
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError('HOPE_ARCHIVE_HOME must be absolute')
        return path
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'HopeArchive'


class DesktopService(local_api.LocalService):
    def __init__(self, home):
        super().__init__()
        self.home = home

    def dispatch(self, method, path, body, token):
        if method == 'GET' and path == '/health':
            return {'status': 'ok', 'defaultOutputDir': str(self.home / 'archives')}
        return super().dispatch(method, path, body, token)


class DesktopHandler(local_api.Handler):
    def handle_json(self):
        supplied = self.headers.get('X-Hope-Desktop', '')
        if not secrets.compare_digest(supplied, self.server.desktop_key):
            self.reply(403, {'error': 'Desktop owner required.'})
            return
        super().handle_json()


def main():
    # Private bootstrap travels through inherited stdin, never process arguments,
    # a file, the frontend bundle, or a network-readable discovery endpoint.
    bootstrap = json.loads(sys.stdin.readline(4096))
    key = bootstrap.get('key', '')
    if not isinstance(key, str) or len(key) < 32:
        raise ValueError('Invalid desktop bootstrap')
    home = user_home().resolve()
    home.mkdir(parents=True, exist_ok=True)
    auth.configure_desktop()
    # Fail before reporting readiness if the distribution is incomplete.
    for name in ('SEND_CODE_PROTOCOL_KEY', 'LOGIN_PROTOCOL_KEY'):
        auth.get_protocol_key(name)
    server = ThreadingHTTPServer(('127.0.0.1', 0), DesktopHandler)
    server.desktop_key = key
    server.service = DesktopService(home)
    listener = threading.Thread(target=server.serve_forever, daemon=True)
    listener.start()
    print(json.dumps({'port': server.server_port}), flush=True)
    try:
        # EOF also handles an unexpectedly closed desktop parent.
        for command in sys.stdin:
            if command.strip() == 'shutdown':
                break
    finally:
        server.shutdown()
        server.server_close()
        server.service.pool.shutdown(wait=True)
        listener.join()


if __name__ == '__main__':
    main()
