"""Rebuildable local FTS5 index; normalized JSON remains the source of truth."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
from datetime import date
from .diary_types import normalized_type, LABELS
from .export_markdown import display_value, EMOTION_LABELS, WEATHER_LABELS

LOCK = threading.RLock()


class SearchError(Exception):
    pass


def profile_dir():
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'HopeArchive'


def text(value):
    return value if isinstance(value, str) else ''


def record(entry, kind):
    if not isinstance(entry, dict):
        raise ValueError('Invalid entry')
    if kind == 'diary':
        category = normalized_type(entry)
        comments = [c for g in entry.get('comments') or [] for c in g.get('items') or []]
        body = '\n'.join(filter(None, [text(entry.get('title')), text(entry.get('original_text')),
            text(entry.get('original_text_secondary')), *[text(b.get('text')) for b in entry.get('content') or []],
            *[text(c.get('text')) for c in comments],
            display_value(entry.get('emotion'), EMOTION_LABELS), display_value(entry.get('weather'), WEATHER_LABELS),
            LABELS.get(category, '未知类型')]))
        day = text(entry.get('note_date'))[:10]
    else:
        # Never index hidden/unopened/cleared capsule body even if raw fields exist.
        if entry.get('status') != 'opened' or (entry.get('metadata') or {}).get('status') == -1:
            return None
        category = 'time_capsule'
        body = '\n'.join(filter(None, [text(entry.get('title')), text(entry.get('keywords')), text(entry.get('content'))]))
        day = text(entry.get('created_at'))[:10]  # explicitly creation date, not unlock date
    return {'date': day, 'category': category, 'kind': kind, 'title': text(entry.get('title')),
            'body': body, 'originalId': str(entry.get('id', ''))}


def snippet(body, query):
    match = re.search(re.escape(query), body, re.IGNORECASE)
    start = max(0, (match.start() if match else 0) - 55)
    value = ('…' if start else '') + body[start:start + max(180, len(query) + 70)]
    if start + max(180, len(query) + 70) < len(body): value += '…'
    return value


class SearchIndex:
    def __init__(self, root, cache=None):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise SearchError('请选择存在的本地归档目录。')
        cache = Path(cache) if cache is not None else profile_dir() / 'search'
        cache.mkdir(parents=True, exist_ok=True)
        self.path = cache / (hashlib.sha256(str(self.root).casefold().encode()).hexdigest() + '.sqlite3')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA secure_delete=ON')
            db.execute('CREATE TABLE IF NOT EXISTS sources(path TEXT PRIMARY KEY, stamp TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS entries(id TEXT PRIMARY KEY, source TEXT, day TEXT, category TEXT, kind TEXT, title TEXT, body TEXT, original_id TEXT)')
            db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(body, tokenize='trigram')")
            return db
        except sqlite3.Error:
            db.close()
            raise SearchError("SQLite FTS5 索引不可用或损坏，请检查本地数据库与运行环境。") from None

    def sync(self, rebuild=False):
        with LOCK:
            db = self.connect()
            try:
                with db:
                    if rebuild:
                        db.execute('DELETE FROM search_fts'); db.execute('DELETE FROM entries'); db.execute('DELETE FROM sources')
                    known = dict(db.execute('SELECT path, stamp FROM sources'))
                    sources, latest = {}, {}
                    paths=[]
                    for name,kind,collection in [('diaries.normalized.json','diary','diaries'),('capsules.normalized.json','capsule','capsules')]:
                        for path in self.root.rglob(name):
                            if path.resolve().is_relative_to(self.root): paths.append((path,kind,collection))
                    paths.sort(key=lambda item:(item[0].stat().st_mtime_ns,str(item[0])))
                    for path,kind,collection in paths:
                        source=str(path.relative_to(self.root));stat=path.stat()
                        sources[source]=f'{stat.st_mtime_ns}:{stat.st_size}'
                    changed=sum(known.get(k)!=v for k,v in sources.items())+len(known.keys()-sources.keys())
                    if changed or rebuild:
                        for path,kind,collection in paths:
                            source=str(path.relative_to(self.root))
                            data=json.loads(path.read_text(encoding='utf-8-sig'))
                            if not isinstance(data,dict) or not isinstance(data.get(collection),list): raise ValueError('Invalid normalized archive')
                            for entry in data[collection]:
                                row=record(entry,kind)
                                if row is None: continue
                                owner=str((entry.get('author') or {}).get('id') or path.relative_to(self.root).parts[0])
                                identity=hashlib.sha256(json.dumps([owner,kind,row['category'],row['originalId']],ensure_ascii=False).encode()).hexdigest()
                                latest[identity]=(source,row)
                        db.execute('DELETE FROM search_fts');db.execute('DELETE FROM entries');db.execute('DELETE FROM sources')
                        for identity,(source,row) in latest.items():
                            cursor=db.execute('INSERT INTO entries VALUES(?,?,?,?,?,?,?,?)',
                                (identity,source,row['date'],row['category'],row['kind'],row['title'],row['body'],row['originalId']))
                            db.execute('INSERT INTO search_fts(rowid,body) VALUES(?,?)',(cursor.lastrowid,row['body']))
                        db.executemany('INSERT INTO sources VALUES(?,?)',sources.items())
                    return {'updatedFiles': changed, 'entries': db.execute('SELECT count(*) FROM entries').fetchone()[0]}
            except (OSError, ValueError, TypeError, AttributeError, sqlite3.Error):
                raise SearchError('无法更新索引，请检查规范化归档文件及目录权限；可修复后重建。') from None
            finally:
                db.close()

    def query(self, query, begin='', end='', category='all', kind='all', offset=0):
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise SearchError('请输入 1–200 字符的关键词。')
        if not isinstance(category, str) or not isinstance(kind, str) or category not in (*LABELS, 'all') or kind not in ('all', 'diary', 'capsule'):
            raise SearchError('筛选类型无效。')
        if type(offset) is not int or offset < 0: raise SearchError('分页位置无效。')
        try:
            if not isinstance(begin, str) or not isinstance(end, str): raise ValueError()
            if begin: date.fromisoformat(begin)
            if end: date.fromisoformat(end)
            if begin and end and begin > end: raise ValueError()
        except (ValueError, TypeError): raise SearchError('日期范围无效。') from None
        self.sync()
        terms, args = [], []
        query = query.strip()
        if len(query) >= 3:
            terms.append('entries.rowid IN (SELECT rowid FROM search_fts WHERE search_fts MATCH ?)')
            args.append('"' + query.replace('"', '""') + '"')
        else:
            # FTS trigram cannot match <3 characters; literal scan handles Chinese short words.
            terms.append('instr(lower(body), lower(?)) > 0'); args.append(query)
        for column, value, operator in [('day', begin, '>='), ('day', end, '<='), ('category', '' if category == 'all' else category, '='), ('kind', '' if kind == 'all' else kind, '=')]:
            if value: terms.append(f'{column} {operator} ?'); args.append(value)
        where = ' AND '.join(terms)
        with LOCK:
            db = self.connect()
            try:
                total = db.execute('SELECT count(*) FROM entries WHERE ' + where, args).fetchone()[0]
                rows = db.execute('SELECT * FROM entries WHERE ' + where + ' ORDER BY day DESC,id LIMIT 50 OFFSET ?', [*args, offset]).fetchall()
                return {'total': total, 'nextOffset': offset + len(rows), 'items': [dict(id=row['id'], date=row['day'], diaryType=row['category'], contentType=row['kind'], title=row['title'], snippet=snippet(row['body'], query)) for row in rows]}
            finally: db.close()

    def detail(self, identity):
        self.sync()
        db = self.connect()
        try:
            row = db.execute('SELECT * FROM entries WHERE id=?', (identity,)).fetchone()
            if row is None: raise SearchError('本地条目不存在或已更新，请重新搜索。')
            return dict(id=row['id'], date=row['day'], diaryType=row['category'], contentType=row['kind'], title=row['title'], body=row['body'])
        finally: db.close()

    def diary_count(self):
        self.sync()
        db = self.connect()
        try:
            return db.execute("SELECT count(*) FROM entries WHERE kind='diary'").fetchone()[0]
        finally: db.close()

    def retrieve(self, question, terms, begin='', end='', category='all', limit=16):
        """Rank diary entries locally for grounded QA; never returns source paths."""
        if (not isinstance(question, str) or not isinstance(terms, list) or
                any(not isinstance(term, str) or not term for term in terms)):
            raise SearchError('检索问题无效。')
        if category not in (*LABELS, 'all') or type(limit) is not int or not 1 <= limit <= 50:
            raise SearchError('检索筛选无效。')
        try:
            if begin: date.fromisoformat(begin)
            if end: date.fromisoformat(end)
            if begin and end and begin > end: raise ValueError()
        except (ValueError, TypeError): raise SearchError('日期范围无效。') from None
        self.sync()
        filters, args = ["kind='diary'"], []
        if begin: filters.append('day>=?'); args.append(begin)
        if end: filters.append('day<=?'); args.append(end)
        if category != 'all': filters.append('category=?'); args.append(category)
        lexical, lexical_args = [], []
        for term in terms:
            if len(term) >= 3:
                lexical.append('entries.rowid IN (SELECT rowid FROM search_fts WHERE search_fts MATCH ?)')
                lexical_args.append('"' + term.replace('"', '""') + '"')
            else:
                lexical.append('instr(lower(body),lower(?))>0'); lexical_args.append(term)
        if lexical:
            filters.append('(' + ' OR '.join(lexical) + ')'); args.extend(lexical_args)
        elif not re.search(r'总结|回顾|最近|这段时间|一周|一月|月份', question):
            return []
        with LOCK:
            db = self.connect()
            try:
                rows = db.execute('SELECT * FROM entries WHERE ' + ' AND '.join(filters), args).fetchall()
            except sqlite3.Error:
                raise SearchError('本地检索失败，请尝试重建索引。') from None
            finally: db.close()
        def score(row):
            body = row['body'].casefold()
            hits = sum((body.count(term.casefold()) * 4 + (6 if term.casefold() in (row['title'] or '').casefold() else 0)) for term in terms)
            exact = 12 if question.strip().casefold() in body else 0
            return hits + exact
        # Resolve equal lexical scores deterministically, preferring newer diary evidence.
        ranked = sorted(rows, key=lambda row: (score(row), row['day'] or '', row['id']), reverse=True)[:limit]
        return [dict(id=row['id'], date=row['day'], diaryType=row['category'], title=row['title'], body=row['body']) for row in ranked]
