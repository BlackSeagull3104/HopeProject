"""Thin application layer: validate one request and orchestrate existing stages."""
from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
import re
import tempfile
import traceback

from .api import fetch_all_diaries
from .normalization import normalize_diaries
from .media import localize
from .export_markdown import export_diaries

# Request value 0 has been exercised; no verified business label for 0 or 2 yet.
NOTE_TYPE_OPTIONS = {'默认日记类型': 0}


class ArchiveError(Exception):
    def __init__(self, message, output_dir=None):
        super().__init__(message)
        self.output_dir = output_dir


@dataclass
class ArchiveResult:
    output_dir: Path
    diary_count: int
    media: dict
    markdown: dict

    @property
    def complete(self):
        return self.media['failed'] == 0 and self.markdown['failed'] == 0


def validate_date_range(begin_date, end_date):
    for value in (begin_date, end_date):
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ArchiveError('日期格式应为 YYYY-MM-DD。')
    try:
        begin, end = date.fromisoformat(begin_date), date.fromisoformat(end_date)
    except ValueError as exc:
        raise ArchiveError('日期无效，请检查年月日。') from exc
    today = date.today()
    if begin > today:
        raise ArchiveError('开始日期不能晚于今天。')
    if end > today:
        raise ArchiveError('结束日期不能晚于今天。')
    if begin > end:
        raise ArchiveError('开始日期不能晚于结束日期。')
    return begin, end


def validate_request(user_id, begin_date, end_date, note_type, output_dir):
    if not isinstance(user_id, str) or not user_id.strip():
        raise ArchiveError('请填写你本人的 User ID。')
    validate_date_range(begin_date, end_date)
    if type(note_type) is not int or note_type not in NOTE_TYPE_OPTIONS.values():
        raise ArchiveError('暂不支持所选日记类型。')
    if output_dir is None or not str(output_dir).strip():
        raise ArchiveError('请选择归档根目录。')
    try:
        root = Path(output_dir).expanduser().resolve()
        if root.exists() and not root.is_dir():
            raise ArchiveError('归档根目录必须是文件夹。')
    except (OSError, ValueError) as exc:
        raise ArchiveError('归档路径无效。') from exc
    return root


def export_archive(user_id, begin_date, end_date, note_type, output_dir, *, on_progress=None):
    """Export one user's archive. Pagination, payload and file details stay here/core-side.

    A fresh run directory is intentional: the downloader never overwrites raw pages.
    on_progress receives stage labels, not unverified percentage estimates.
    """
    root = validate_request(user_id, begin_date, end_date, note_type, output_dir)
    try:
        root.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix='hope-archive-' + datetime.now().strftime('%Y%m%d-%H%M%S-'), dir=root))
    except OSError as exc:
        raise ArchiveError('无法创建归档目录，请检查路径和写入权限。') from exc
    stage = '获取日记'
    def report(message):
        if on_progress is not None:
            on_progress(message)
    try:
        report('正在获取日记…')
        entries = fetch_all_diaries(user_id.strip(), begin_date, end_date, note_type=note_type, data_dir=run_dir)
        stage = '标准化'
        report('正在标准化…')
        document = normalize_diaries(entries)
        processed = run_dir / 'processed'
        processed.mkdir(parents=True, exist_ok=True)
        with (processed / 'diaries.normalized.json').open('x', encoding='utf-8') as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        stage = '保存媒体'
        report('正在保存媒体…')
        archive = run_dir / 'archive'
        media = localize(document, archive)
        stage = '生成 Markdown'
        report('正在生成 Markdown…')
        manifest = json.loads((archive / 'media_manifest.json').read_text(encoding='utf-8'))
        markdown = export_diaries(document, manifest, archive)
        result = ArchiveResult(run_dir, len(entries), media, markdown)
        report('归档完成' if result.complete else '归档部分完成，请查看结果说明。')
        return result
    except Exception as exc:
        # Keep diagnostics local; UI receives a short stage-specific message only.
        try:
            (run_dir / 'error.log').write_text(traceback.format_exc(), encoding='utf-8')
        except OSError:
            pass
        messages = {'获取日记': '获取日记失败，请检查网络、User ID 或服务返回状态。',
                    '标准化': '数据标准化失败，已保留原始响应。',
                    '保存媒体': '保存媒体失败，请检查网络、磁盘空间或目录权限。',
                    '生成 Markdown': 'Markdown 导出失败，已保存的数据仍保留。'}
        raise ArchiveError(messages[stage], run_dir) from exc
