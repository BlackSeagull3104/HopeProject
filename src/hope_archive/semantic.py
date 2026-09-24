"""Optional local retrieval: scoped durable derived vectors + v3 RRF(60)."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import threading

from . import semantic_model as model
from .search import LOCK, profile_dir, snippet

FALLBACK = '语义检索暂时不可用，已使用 FTS5 完成本次搜索。'
SCHEMA = '1'


def fuse(*rankings):
    scores = {}
    for ranking in rankings:
        for rank, identity in enumerate(dict.fromkeys(ranking), 1):
            scores[identity] = scores.get(identity, 0) + 1 / (60 + rank)
    return sorted(scores, key=lambda identity: (-scores[identity], identity))


def snapshot(index):
    """Only safe diary evidence from the existing normalized-derived FTS store."""
    with LOCK:
        index.sync()
        db = index.connect()
        try:
            rows = db.execute("SELECT id,day,category,title,body FROM entries WHERE kind='diary' ORDER BY id").fetchall()
            return [dict(id=r['id'], date=r['day'], diaryType=r['category'], title=r['title'], body=r['body']) for r in rows]
        finally: db.close()


def fingerprints(entries):
    return {e['id']: hashlib.sha256(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest() for e in entries}


def vector(values):
    if len(values) != 384 or not all(math.isfinite(v) for v in values): raise ValueError('Invalid vector')
    length = math.sqrt(sum(v * v for v in values))
    if not .99 <= length <= 1.01: raise ValueError('Invalid vector norm')
    return values


class Worker:
    def __init__(self, directory):
        if getattr(sys, 'frozen', False):
            command = [str(Path(sys.executable).parent / 'ocr-runtime' / 'hope-archive-ocr.exe'), '--semantic']
        else:
            command = [sys.executable, '-B', '-X', 'utf8', '-m', 'hope_archive.semantic_worker']
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        if not getattr(sys, 'frozen', False):
            env['PYTHONPATH'] = os.pathsep.join([str(Path(__file__).resolve().parents[1]), *[p for p in sys.path if p]])
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.reader = ThreadPoolExecutor(max_workers=1)
        try: self.exchange({'model': str(directory)})
        except Exception:
            self.close()
            raise

    def exchange(self, body):
        self.process.stdin.write((json.dumps(body, ensure_ascii=True) + '\n').encode())
        self.process.stdin.flush()
        try:
            line = self.reader.submit(self.process.stdout.readline).result(timeout=120)
            result = json.loads(line)
            if isinstance(result, dict) and 'error' in result: raise ValueError('Runtime')
            return result
        except Exception:
            self.close()
            raise ValueError('本地语义运行时不可用。') from None

    def __call__(self, text, kind):
        return self.exchange({'text': text, 'kind': kind})

    def close(self):
        if self.process.poll() is None: self.process.kill()
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()
        self.reader.shutdown(wait=False, cancel_futures=True)


class VectorIndex:
    def __init__(self, index, home):
        self.scope = hashlib.sha256(str(index.root).casefold().encode()).hexdigest()
        self.path = Path(home) / (self.scope + '.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            db.execute('PRAGMA secure_delete=ON')
            db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY,fingerprint TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS chunks(id TEXT,ordinal INTEGER,text TEXT,vector BLOB,PRIMARY KEY(id,ordinal))')
            return db
        except Exception:
            db.close()
            raise

    def metadata(self):
        return {'schema': SCHEMA, 'model': model.MODEL, 'version': model.VERSION, 'dimension': '384', 'scope': self.scope}

    def ready(self, entries):
        if not self.path.is_file(): return False
        db = self.connect()
        try:
            return dict(db.execute('SELECT * FROM meta')) == self.metadata() and dict(db.execute('SELECT * FROM docs')) == fingerprints(entries)
        finally: db.close()

    def sync(self, entries, encode, rebuild=False):
        try: db = self.connect()
        except sqlite3.DatabaseError:
            # Only this derived, exact scoped index is discarded on explicit rebuild.
            if not rebuild: raise
            self.path.unlink()
            db = self.connect()
        try:
            with db:
                if rebuild or dict(db.execute('SELECT * FROM meta')) != self.metadata():
                    db.execute('DELETE FROM chunks'); db.execute('DELETE FROM docs'); db.execute('DELETE FROM meta')
                previous = dict(db.execute('SELECT * FROM docs'))
                current = fingerprints(entries)
                changed = 0
                for identity in previous.keys() - current.keys():
                    db.execute('DELETE FROM chunks WHERE id=?', (identity,))
                    db.execute('DELETE FROM docs WHERE id=?', (identity,))
                for entry in entries:
                    identity = entry['id']
                    if previous.get(identity) == current[identity]: continue
                    chunks = encode(entry['body'], 'passage')
                    if not chunks: raise ValueError('Missing semantic chunks')
                    db.execute('DELETE FROM chunks WHERE id=?', (identity,))
                    for ordinal, chunk in enumerate(chunks):
                        blob = struct.pack('<384f', *vector(chunk['vector']))
                        db.execute('INSERT INTO chunks VALUES(?,?,?,?)', (identity, ordinal, chunk['text'], blob))
                    db.execute('INSERT OR REPLACE INTO docs VALUES(?,?)', (identity, current[identity]))
                    changed += 1
                db.executemany('INSERT OR REPLACE INTO meta VALUES(?,?)', self.metadata().items())
            return changed
        finally: db.close()

    def rank(self, values, allowed):
        query = vector(values)
        db = self.connect()
        try:
            scores, excerpts = {}, {}
            for identity, text, blob in db.execute('SELECT id,text,vector FROM chunks ORDER BY id,ordinal'):
                if identity not in allowed: continue
                score = sum(a * b for a, b in zip(query, vector(struct.unpack('<384f', blob)), strict=True))
                if identity not in scores or score > scores[identity]: scores[identity], excerpts[identity] = score, text
            if set(scores) != set(allowed): raise ValueError('Incomplete semantic index')
            return sorted(scores, key=lambda i: (-scores[i], i)), excerpts
        finally: db.close()


class SemanticService:
    def __init__(self, pool, home=None, factory=Worker):
        self.pool = pool
        self.home = Path(home) if home is not None else profile_dir() / 'semantic'
        self.factory = factory
        self.lock = threading.RLock()
        self.runtime_lock = threading.RLock()
        self.states = {}
        self.install_state = ''
        self.worker = None
        self.stamp = None
        self.closed = False

    def derived(self, index): return VectorIndex(index, self.home / 'indexes')

    def encoder(self):
        directory = model.installed(self.home)
        if directory is None: raise ValueError('Missing model')
        stamp = (str(directory), tuple((p.stat().st_size, p.stat().st_mtime_ns) for p in (directory / name for name in model.FILES)))
        if self.worker is None or stamp != self.stamp:
            self.drop_worker()
            model.verify(directory)
            self.worker = self.factory(directory)
            self.stamp = stamp
        return self.worker

    def drop_worker(self):
        if self.worker is not None: self.worker.close()
        self.worker = None
        self.stamp = None

    def status(self, index):
        derived = self.derived(index)
        with self.lock:
            state = self.install_state or self.states.get(derived.scope, '')
        if state not in ('downloading', 'verifying', 'indexing', 'download_failed', 'verification_failed', 'index_failed'):
            try:
                if model.installed(self.home) is None: state = 'not_installed'
                else: state = 'ready' if derived.ready(snapshot(index)) else 'rebuild_required'
            except Exception: state = 'rebuild_required'
        return {'state': state, 'model': model.MODEL, 'downloadBytes': model.DOWNLOAD_BYTES,
                'local': True, 'storage': '应用管理的本机缓存（不在日记归档中）'}

    def start(self, index, download=False, rebuild=False):
        scope = self.derived(index).scope
        with self.lock:
            if self.closed: raise ValueError('服务已关闭。')
            if self.install_state in ('downloading', 'verifying') or 'indexing' in self.states.values():
                return self.status(index)
            if download: self.install_state = 'downloading'
            else: self.states[scope] = 'indexing'
            self.pool.submit(self.run, index, download, rebuild)
        return self.status(index)

    def run(self, index, download, rebuild):
        scope = self.derived(index).scope
        try:
            if download:
                def progress(state):
                    with self.lock: self.install_state = state
                model.install(self.home, progress, lambda: self.closed)
                with self.lock: self.install_state = ''; self.states[scope] = 'installed'
            with self.runtime_lock:
                if self.closed: return
                with self.lock: self.states[scope] = 'indexing'
                encoder = self.encoder()
                def encode(text, kind):
                    if self.closed: raise ValueError('Service closed')
                    if len(text) > 500000: raise ValueError('Diary exceeds semantic safety limit')
                    return encoder(text, kind)
                self.derived(index).sync(snapshot(index), encode, rebuild)
            with self.lock: self.states[scope] = 'ready'
        except Exception as exc:
            with self.lock:
                if self.install_state:
                    self.install_state = 'verification_failed' if isinstance(exc, model.IntegrityError) else 'download_failed'
                else: self.states[scope] = 'index_failed'
            with self.runtime_lock: self.drop_worker()

    def retrieve(self, index, question, terms, begin, end, category, limit):
        lexical = index.retrieve(question, terms, begin, end, category, 200)
        fallback = (lexical[:limit], {'mode': 'FTS5', 'fallback': FALLBACK})
        if self.status(index)['state'] != 'ready': return fallback
        try:
            with self.runtime_lock:
                entries = snapshot(index)
                derived = self.derived(index)
                if not derived.ready(entries): return fallback
                allowed = {e['id']: e for e in entries if
                    (not begin or e['date'] >= begin) and (not end or e['date'] <= end) and
                    (category == 'all' or e['diaryType'] == category)}
                if not allowed: return [], {'mode': 'Hybrid', 'fallback': ''}
                result = self.encoder()(question, 'query')
                ranked, excerpts = derived.rank(result[0]['vector'], allowed)
                identities = fuse([e['id'] for e in lexical], ranked[:200])[:limit]
                # Feed matching long-entry passages to existing bounded AI chunking.
                return [dict(allowed[i], body=excerpts.get(i, allowed[i]['body'])) for i in identities], {'mode': 'Hybrid', 'fallback': ''}
        except Exception:
            with self.lock: self.states[self.derived(index).scope] = 'index_failed'
            with self.runtime_lock: self.drop_worker()
            return fallback

    def close(self):
        self.closed = True
        with self.runtime_lock: self.drop_worker()


class RetrievalIndex:
    """Only retrieve is replaced; Review/Selected/source-lock remain source scoped."""
    def __init__(self, index, service, mode):
        if mode not in ('FTS5', 'Hybrid'): raise ValueError('检索模式无效。')
        self.index, self.service, self.mode = index, service, mode
        self.retrieval = {'mode': 'FTS5', 'fallback': ''}

    def __getattr__(self, name): return getattr(self.index, name)

    def retrieve(self, question, terms, begin='', end='', category='all', limit=16):
        if self.mode == 'FTS5': return self.index.retrieve(question, terms, begin, end, category, limit)
        entries, self.retrieval = self.service.retrieve(self.index, question, terms, begin, end, category, limit)
        return entries

    def related_query(self, query, terms, begin='', end='', category='all', offset=0):
        if type(offset) is not int or not 0 <= offset <= 200: raise ValueError('分页位置无效。')
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200: raise ValueError('请输入 1–200 字符的关键词。')
        entries = self.retrieve(query, terms, begin, end, category, 200)
        page = entries[offset:offset + 50]
        return {'total': len(entries), 'nextOffset': offset + len(page), 'limited': len(entries) == 200,
                'retrieval': self.retrieval, 'items': [dict(id=e['id'], date=e['date'], diaryType=e['diaryType'],
                    contentType='diary', title=e['title'], snippet=snippet(e['body'], query)) for e in page]}
