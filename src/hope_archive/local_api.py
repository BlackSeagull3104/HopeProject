"""Loopback-only JSON adapter. Run with python -m hope_archive.local_api."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time

from . import application, auth, capsules
from .diary_types import filter_value, DiaryType, normalized_type
from .export_documents import ExportFormat, export_document

PROJECT = Path(__file__).resolve().parents[2]
ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173'}


class RequestError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def fields(body, required, optional=()):
    if not isinstance(body, dict) or set(body) - set(required) - set(optional):
        raise RequestError(400, '请求包含不支持的字段。')
    for key in required:
        if not isinstance(body.get(key), str) or not body[key].strip():
            raise RequestError(400, '请填写所有必填项。')


class LocalService:
    def __init__(self):
        self.lock = threading.RLock()
        self.sessions = {}
        self.jobs = {}
        self.resend_at = 0
        self.auth_busy = False
        self.pool = ThreadPoolExecutor(max_workers=1)

    def session(self, token):
        with self.lock:
            value = self.sessions.get(token)
            if value is None or value['expires'] < time.monotonic():
                self.sessions.pop(token, None)
                raise RequestError(401, '登录状态已失效，请重新登录。')
            return value

    def authenticate(self, action, body):
        fields(body, ['mobile'] if action == 'send-code' else ['mobile', 'secret'])
        with self.lock:
            if self.auth_busy:
                raise RequestError(409, '认证请求进行中，请等待。')
            if action == 'send-code' and time.monotonic() < self.resend_at:
                raise RequestError(429, '请等待 60 秒后再发送验证码。')
            self.auth_busy = True
            if action == 'send-code':
                self.resend_at = time.monotonic() + 60
        try:
            if action == 'send-code':
                auth.send_security_code(body['mobile'].strip())
                return {'success': True}
            login = auth.login_by_security_code if action == 'code' else auth.login_by_password
            user = login(body['mobile'].strip(), body['secret'])
            token = secrets.token_urlsafe(32)
            with self.lock:
                self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > time.monotonic()}
                nickname = user.nickname.strip() if isinstance(user.nickname, str) else ''
                self.sessions[token] = {'userId': user.user_id, 'displayName': nickname or 'Hope 用户', 'expires': time.monotonic() + 12 * 3600}
            return {'token': token, 'userId': user.user_id, 'displayName': nickname or 'Hope 用户'}
        except auth.AuthError as exc:
            # Never return untrusted server messages or the raw response.
            raise RequestError(400, str(exc)) from None
        finally:
            with self.lock:
                self.auth_busy = False

    def start(self, kind, body, token):
        user = self.session(token)
        if kind == 'archive':
            fields(body, ['beginDate', 'endDate', 'outputDir'], ['diaryType'])
            application.validate_request(user['userId'], body['beginDate'], body['endDate'], filter_value(body.get('diaryType', 'all')), body['outputDir'])
        else:
            fields(body, ['inputPath', 'archiveDir'], ['outputDir', 'format', 'beginDate', 'endDate', 'diaryType'])
            DiaryType(body.get('diaryType', 'all'))
            try:
                ExportFormat(body.get('format', 'markdown'))
            except (ValueError, TypeError):
                raise RequestError(400, '不支持的导出格式。') from None
            if 'beginDate' in body or 'endDate' in body:
                application.validate_date_range(body.get('beginDate'), body.get('endDate'))
            if 'outputDir' in body and not isinstance(body['outputDir'], str):
                raise RequestError(400, '导出目录格式无效。')
        with self.lock:
            if any(j['state'] == 'running' for j in self.jobs.values()):
                raise RequestError(409, '已有任务进行中，请等待完成。')
            # Bounded in-memory history; no diary contents or credentials in jobs.
            if len(self.jobs) >= 100:
                self.jobs.pop(next(iter(self.jobs)))
            job_id = secrets.token_urlsafe(16)
            self.jobs[job_id] = {'owner': token, 'state': 'running', 'stage': '正在准备…', 'kind': kind}
            self.pool.submit(self.run, job_id, kind, dict(body), user['userId'])
            return {'jobId': job_id}

    def update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)

    def run(self, job_id, kind, body, user_id):
        try:
            if kind == 'archive':
                result = application.export_archive(user_id, body['beginDate'], body['endDate'], filter_value(body.get('diaryType', 'all')),
                    body['outputDir'], on_progress=lambda stage: self.update(job_id, stage=stage))
                summary = {'outputDir': str(result.output_dir), 'diaryCount': result.diary_count,
                           'media': result.media, 'markdown': result.markdown}
                complete = result.complete
            else:
                format = body.get('format', 'markdown')
                self.update(job_id, stage='正在生成导出文件…')
                document = json.loads(Path(body['inputPath']).expanduser().read_text(encoding='utf-8-sig'))
                if not isinstance(document, dict) or not isinstance(document.get('diaries'), list):
                    raise ValueError('Invalid normalized document')
                # Legacy archives may lack author IDs. Reject known mismatches.
                for diary in document['diaries']:
                    owner = (diary.get('author') or {}).get('id')
                    if owner is not None and str(owner) != user_id:
                        raise RequestError(403, '归档中的作者与当前登录账号不符。')
                archive = Path(body['archiveDir']).expanduser().resolve()
                if not archive.is_dir():
                    raise ValueError('Missing archive directory')
                manifest_path = archive / 'media_manifest.json'
                manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
                output = Path(body['outputDir']).expanduser().resolve() if body.get('outputDir', '').strip() else archive
                if output.exists() and not output.is_dir():
                    raise RequestError(400, '输出路径必须是文件夹。')
                if 'beginDate' in body:
                    begin, end = application.validate_date_range(body['beginDate'], body['endDate'])
                    document = dict(document, diaries=[d for d in document['diaries']
                        if begin.isoformat() <= (d.get('note_date') or '')[:10] <= end.isoformat()])
                category = body.get('diaryType', 'all')
                if category != 'all':
                    document = dict(document, diaries=[d for d in document['diaries'] if normalized_type(d) == category])
                stats = export_document(document, manifest, archive, output, format)
                summary = {'outputDir': str(output), 'diaryCount': len(document['diaries']), 'export': stats, 'format': format}
                if format == 'markdown':
                    summary['markdown'] = stats
                complete = stats['failed'] == 0
            self.update(job_id, state='completed' if complete else 'partial',
                        stage='已完成' if complete else '部分完成，请检查失败数量。', result=summary)
        except application.ArchiveError as exc:
            self.update(job_id, state='failed', stage=str(exc), outputDir=str(exc.output_dir) if exc.output_dir else None)
        except RequestError as exc:
            self.update(job_id, state='failed', stage=str(exc))
        except Exception:
            self.update(job_id, state='failed', stage='处理失败，请检查文件格式、路径和目录权限；已有文件保留。')

    def capsule_request(self, path, body, token):
        user = self.session(token)
        if path == '/capsules/list':
            fields(body, ['status', 'outputDir'], ['offset'])
            capsules.CapsuleStatus(body['status'])
            offset = body.get('offset', 0)
            if type(offset) is not int or offset < 0:
                raise RequestError(400, '分页位置无效。')
        elif path == '/capsules/detail':
            fields(body, ['id'])
        else:
            fields(body, ['id', 'key'])
        with self.lock:
            if user.get('capsule_busy'):
                raise RequestError(409, '时间胶囊请求进行中，请等待。')
            user['capsule_busy'] = True
        try:
            archive = user.get('capsule_archive')
            if path == '/capsules/list':
                if archive is None:
                    if offset:
                        raise RequestError(400, '请先加载第一页。')
                    archive = capsules.CapsuleArchive(user['userId'], body['outputDir'])
                    user['capsule_archive'] = archive
                elif Path(body['outputDir']).expanduser().resolve() != archive.root.parent:
                    raise RequestError(400, '当前会话请使用原归档目录；更换目录需重新登录。')
                return archive.list(body['status'], offset)
            if archive is None:
                raise RequestError(400, '请先加载当前账号的时间胶囊列表。')
            if path == '/capsules/detail':
                return archive.detail(body['id'])
            return archive.media(body['id'], body['key'])
        except capsules.CapsuleError as exc:
            raise RequestError(400, str(exc)) from None
        finally:
            with self.lock:
                user['capsule_busy'] = False

    def dispatch(self, method, path, body, token):
        if method == 'GET' and path == '/health':
            return {'status': 'ok', 'defaultOutputDir': str(PROJECT / 'data')}
        if method == 'POST' and path in ('/auth/send-code', '/auth/login/code', '/auth/login/password'):
            return self.authenticate(path.rsplit('/', 1)[1], body)
        self.session(token)
        if method == 'POST' and path in ('/capsules/list', '/capsules/detail', '/capsules/media'):
            return self.capsule_request(path, body, token)
        if method == 'POST' and path == '/auth/logout':
            with self.lock:
                self.sessions.pop(token, None)
            return {'success': True}
        if method == 'POST' and path in ('/archive/download', '/export/markdown', '/export/document'):
            return self.start('archive' if path == '/archive/download' else 'export', body, token)
        if method == 'GET' and path.startswith('/jobs/'):
            with self.lock:
                job = self.jobs.get(path.removeprefix('/jobs/'))
                if not job or job['owner'] != token:
                    raise RequestError(404, '找不到任务。')
                return deepcopy({k: v for k, v in job.items() if k != 'owner'})
        raise RequestError(404, '接口不存在。')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No access logs, request bodies, credentials or session headers.

    def do_GET(self):
        self.handle_json()

    def do_POST(self):
        self.handle_json()

    def handle_json(self):
        try:
            self.connection.settimeout(35)
            body = None
            if self.command == 'POST':
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384:
                    raise RequestError(413, '请求大小无效。')
                # Consume the bounded body before rejecting headers: closing with
                # unread data can reset the connection on Windows.
                raw = self.rfile.read(length)
            port = self.server.server_port
            if self.headers.get('Host') not in {f'localhost:{port}', f'127.0.0.1:{port}'}:
                raise RequestError(403, '仅接受本机请求。')
            origin = self.headers.get('Origin')
            if origin is not None and origin not in ORIGINS:
                raise RequestError(403, '请求来源不受支持。')
            if self.command == 'POST':
                if self.headers.get('Content-Type') != 'application/json' or self.headers.get('X-Hope-Client') != 'react':
                    raise RequestError(415, '需要 JSON 客户端请求。')
                body = json.loads(raw)
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            result = self.server.service.dispatch(self.command, self.path, body, token)
            self.reply(200, result)
        except RequestError as exc:
            self.reply(exc.status, {'error': str(exc)})
        except application.ArchiveError as exc:
            self.reply(400, {'error': str(exc)})
        except (ValueError, UnicodeError):
            self.reply(400, {'error': '请求格式无效。'})
        except Exception:
            self.reply(500, {'error': '本地服务未能完成请求，请检查配置或服务状态。'})

    def reply(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode('utf-8')
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(payload)
        except (OSError, TimeoutError):
            pass


def make_server(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.service = LocalService()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    server = make_server(parser.parse_args().port)
    print(f'Hope Archive local API: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        server.service.pool.shutdown(wait=True)


if __name__ == '__main__':
    main()
