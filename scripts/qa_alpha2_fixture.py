"""Loopback-only QA server: production frontend + real service, synthetic transports.

Never shipped by packaging specs. No Hope login, real keys, or paid model calls.
All writes use a fresh isolated temporary profile. Stop with Ctrl+C.
"""
import io
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from hope_archive import ai, api, local_api
from hope_archive.desktop_api import DesktopService


class MemoryStore:
    def __init__(self): self.values = {}
    def read(self, key): return self.values.get(key)
    def write(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)


class FixtureProvider:
    def __init__(self, config, key): self.config = config
    def list_models(self): return ['fixture-success', 'fixture-fail']
    def test_connection(self): return {'success': True, 'message': '合成连接测试通过。'}
    def chat(self, messages):
        if self.config['model'] == 'fixture-fail': raise ai.AIError('合成服务商暂时不可用。')
        return '合成日记记录了 NLP 学习和公园散步。[来源 1]'


class FixtureService(DesktopService):
    def authenticate(self, action, body):
        token = 'synthetic-session'
        self.sessions[token] = dict(userId='synthetic-user', displayName='合成 QA 用户', expires=time.monotonic()+3600)
        return dict(token=token, userId='synthetic-user', displayName='合成 QA 用户')


def response(request, **kwargs):
    payload = json.loads(request.data)
    day = payload['beginDate']
    entries = [dict(dairyId='qa-1', noteDate=day, noteType=1,
                    dairy='合成 QA：今天学习 NLP，晚上在公园散步。主动书写 13800000000。',
                    user=dict(id='synthetic-user', nickName='合成作者', mobile='METADATA-CANARY'),
                    commentList=[])]
    return io.BytesIO(json.dumps(dict(status=1, datas=dict(total=1, list=entries))).encode())


class Handler(local_api.Handler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            self.path = self.path[4:]
            return super().do_GET()
        relative = unquote(self.path.split('?')[0]).lstrip('/') or 'index.html'
        base = (ROOT/'frontend/vite-app/dist').resolve()
        target = (base/relative).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            self.send_error(404); return
        import mimetypes
        content = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers(); self.wfile.write(content)

    def do_POST(self):
        if not self.path.startswith('/api/'):
            self.send_error(404); return
        self.path = self.path[4:]
        super().do_POST()


if __name__ == '__main__':
    with TemporaryDirectory(prefix='hope-alpha2-qa-') as tmp:
        service = FixtureService(Path(tmp)/'profile')
        service.ai_settings = ai.AISettings(MemoryStore(), FixtureProvider)
        service.dispatch('POST', '/settings/save', {'exportRoot': str(Path(tmp)/'output')}, None)
        local_api.ORIGINS.add('http://127.0.0.1:5194')
        server = ThreadingHTTPServer(('127.0.0.1', 5194), Handler)
        server.service = service
        print('Synthetic QA server: http://127.0.0.1:5194', flush=True)
        try:
            with patch.object(api, 'urlopen', response): server.serve_forever()
        except KeyboardInterrupt: pass
        finally:
            server.server_close()
            if hasattr(service, 'semantic_service'): service.semantic_service.close()
            if hasattr(service, 'ocr_jobs'): service.ocr_jobs.close()
            service.pool.shutdown()
