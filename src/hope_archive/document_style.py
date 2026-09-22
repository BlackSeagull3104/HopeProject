"""Renderer-independent reading style, in points (CSS px * 72/96).

Typography reference: VS Code default Markdown, 14px / 22px. Image
percentages remain those of the accepted Markdown export. No reader theme
is applied to or written into the user's Markdown file.
"""
from dataclasses import dataclass
import re

PAGE = (595.28, 841.89)
MARGIN_X = 56
MARGIN_Y = 54
BODY_WIDTH = PAGE[0] - MARGIN_X * 2
IMAGE_HEIGHT = 360  # Existing Markdown 480px cap.
IMAGE_GAP_FRACTION = .02
LATIN_FONT = 'Segoe UI'
CJK_FONT = 'Microsoft YaHei'


@dataclass(frozen=True)
class TextStyle:
    size: float = 10.5
    leading: float = 16.5
    before: float = 0
    after: float = 12
    bold: bool = False
    keep_next: bool = False
    rule: bool = False


BODY = TextStyle()
STYLES = {
    'heading': TextStyle(21, 26.25, 0, 12, True, True, True),
    'title': TextStyle(15.75, 19.6875, 18, 12, True, True, True),
    'subheading': TextStyle(15.75, 19.6875, 18, 12, True, True, True),
    'text': BODY, 'metadata': BODY, 'comment': BODY, 'missing': BODY,
}


def paragraphs(value):
    """Blank lines separate paragraphs; keep explicit line breaks within each."""
    return [p for p in re.split(r'\n[ \t]*\n+', str(value).replace('\r\n', '\n')) if p.strip()]


class CommentText(str):
    """Plain-text compatible comment carrying labelled author runs."""
    def __new__(cls, runs, body):
        value = super().__new__(cls, ''.join(text for text, _ in runs) + body)
        value.runs, value.body = tuple(runs), body
        return value


def comment_text(comment, authors):
    from .export_markdown import person_name
    author = person_name(comment)
    runs = []
    if comment.get('reply_to_id') is not None:
        runs.append(('↳ ', False))
    runs.append((author or '作者未知', bool(author)))
    if comment.get('reply_to_id') is not None:
        target = comment.get('to_name') or authors.get(comment['reply_to_id']) or (comment.get('recipient') or {}).get('name')
        runs.extend([(' 回复 ', False), (target, True)] if target else [('（回复对象未知）', False)])
    runs.append(('：', False))
    return CommentText(runs, comment.get('text') or '')
