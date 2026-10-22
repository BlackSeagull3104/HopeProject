"""Packaged desktop adapter; existing development API and Hope core stay unchanged."""
from http.server import ThreadingHTTPServer
import hashlib
import json
import math
import time
import os
from pathlib import Path
import secrets
import sys
import threading

from . import auth, local_api
from .secure_store import WindowsCredentialStore, SecretStoreError


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
        self.search_cache = home / "search"
        self.login_store = None
        self.restored_token = None

    def saved_login(self):
        if self.login_store is None:
            scope = hashlib.sha256(str(self.home.resolve()).casefold().encode()).hexdigest()
            self.login_store = WindowsCredentialStore('HopeArchive/Login/v1/' + scope + '/')
        return self.login_store

    def authenticate(self, action, body):
        if action == 'send-code': return super().authenticate(action, body)
        local_api.fields(body, ['mobile', 'secret'], ['remember'])
        remember = body.get('remember', False)
        if type(remember) is not bool: raise local_api.RequestError(400, '登录保留选项无效。')
        with self.lock:
            result = super().authenticate(action, {k: body[k] for k in ('mobile', 'secret')})
            try:
                store = self.saved_login()
                # Switching accounts also removes any previous remembered identity.
                store.delete('current')
                if remember:
                    now = time.time()
                    value = {k: result[k] for k in ('userId', 'displayName')}
                    if 'specialExperience' in result:
                        value['specialExperience'] = result['specialExperience'] is True
                    store.write('current', json.dumps(dict(version=1, issued=now, expires=now + 12*3600, identity=value)))
            except (SecretStoreError, OSError, UnicodeError):
                self.sessions.clear()
                self.restored_token = None
                raise local_api.RequestError(503, '无法更新安全登录存储，请检查 Windows 凭据管理器后重试。') from None
            self.sessions = {result['token']: self.sessions[result['token']]}
            self.restored_token = result['token']
            return result

    def restore_login(self):
        with self.lock:
            try:
                if self.restored_token in self.sessions:
                    value = self.session(self.restored_token)
                    return {'session': dict(token=self.restored_token, **{k: value[k] for k in ('userId', 'displayName', 'specialExperience') if k in value})}
                store = self.saved_login()
                raw = store.read('current')
                if raw is None: return {'session': None}
                try:
                    saved = json.loads(raw)
                    now = time.time()
                    if not (isinstance(saved, dict) and set(saved) == {'version', 'issued', 'expires', 'identity'} and type(saved['version']) is int and saved['version'] == 1): raise ValueError()
                    issued, expires = saved['issued'], saved['expires']
                    if not (all(type(v) in (int, float) and math.isfinite(v) for v in (issued, expires))): raise ValueError()
                    if not (issued <= now < expires and 0 < expires - issued <= 12*3600): raise ValueError()
                    identity = saved['identity']
                    if not (isinstance(identity, dict) and set(identity) in ({'userId', 'displayName'}, {'userId', 'displayName', 'specialExperience'})): raise ValueError()
                    if not (all(isinstance(identity[k], str) and 0 < len(identity[k]) <= 512 for k in ('userId', 'displayName'))): raise ValueError()
                    if not ('specialExperience' not in identity or type(identity['specialExperience']) is bool): raise ValueError()
                except (ValueError, TypeError, KeyError):
                    store.delete('current')
                    return {'session': None}
                token = secrets.token_urlsafe(32)
                self.sessions = {token: dict(identity, expires=time.monotonic() + expires - now)}
                self.restored_token = token
                return {'session': dict(identity, token=token)}
            except local_api.RequestError:
                self.saved_login().delete('current')
                self.restored_token = None
                return {'session': None}
            except (SecretStoreError, OSError, UnicodeError):
                raise local_api.RequestError(503, '无法读取安全登录状态，请重新登录。') from None


    def dispatch(self, method, path, body, token):
        if method == 'POST' and path == '/auth/restore':
            local_api.fields(body, [])
            return self.restore_login()
        if method == 'POST' and path == '/auth/logout':
            local_api.fields(body, [])
            with self.lock:
                # Permit explicit logout even after the in-memory session expires.
                try: self.saved_login().delete('current')
                except (SecretStoreError, OSError):
                    raise local_api.RequestError(503, '未能清除保存的登录状态，请重试退出登录。') from None
                self.sessions.clear()
                self.restored_token = None
            return {'success': True}
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
        if hasattr(server.service, 'runtime_component'):
            server.service.runtime_component.close()
        if hasattr(server.service, 'semantic_service'):
            server.service.semantic_service.close()
        if hasattr(server.service, 'ocr_jobs'):
            server.service.ocr_jobs.close()
        server.shutdown()
        server.server_close()
        server.service.pool.shutdown(wait=True)
        listener.join()


if __name__ == '__main__':
    main()
