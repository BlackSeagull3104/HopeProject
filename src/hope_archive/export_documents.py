"""Local normalized-diary exporters; Markdown remains the existing implementation."""
from datetime import datetime
from enum import Enum
from html import escape
from io import BytesIO
import hashlib
import os
from pathlib import Path
import zipfile

from PIL import Image, ImageOps
from .export_markdown import (diary_path, display_value, EMOTION_LABELS, WEATHER_LABELS,
                              local_media, person_name, export_diaries)


class ExportFormat(str, Enum):
    MARKDOWN = 'markdown'
    TEX = 'tex'
    PDF = 'pdf'
    DOCX = 'docx'


def fit_image(width, height, max_width=450, max_height=600):
    if width <= 0 or height <= 0:
        raise ValueError('Invalid image dimensions')
    scale = min(max_width / width, max_height / height, 1)
    return width * scale, height * scale


def image_parts(path):
    """Normalize orientation and split very tall screenshots without stretching."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
        width, height = image.size
        step = max(1, int(width * 1.6)) if height / width > 3 else height
        for top in range(0, height, step):
            part = image.crop((0, top, width, min(top + step, height)))
            data = BytesIO()
            part.save(data, format='PNG')
            yield data.getvalue(), part.size


def blocks(diary, manifest, archive):
    yield 'heading', (diary.get('note_date') or '日期未知')[:10]
    if diary.get('title'):
        yield 'text', str(diary['title'])
    for field, label, mapping in [('emotion', '情绪', EMOTION_LABELS), ('weather', '天气', WEATHER_LABELS)]:
        value = display_value(diary.get(field), mapping)
        if value is not None:
            yield 'text', f'{label}：{value}'
    content = diary.get('content') or []
    for block in content:
        if block.get('text'):
            yield 'text', block['text']
        for media in block.get('media') or []:
            local = local_media(media.get('url'), manifest, archive, archive / 'unused.md')
            if block.get('kind') == 'image' and local:
                for data, size in image_parts(local[0]):
                    yield 'image', (data, fit_image(*size))
            else:
                yield 'text', '[本地媒体不可用]' if not local else f'[{block.get("kind", "媒体")}：{local[0].name}]'
    if not any(b.get('text') or b.get('media') for b in content) and diary.get('original_text'):
        yield 'text', diary['original_text']
    if diary.get('original_text_secondary'):
        yield 'text', diary['original_text_secondary']
    comments = [c for group in diary.get('comments') or [] for c in group.get('items') or []]
    authors = {c.get('id'): person_name(c) for c in comments if c.get('id') is not None}
    if comments:
        yield 'heading', '留言'
    for comment in comments:
        author = person_name(comment) or '作者未知'
        reply = ''
        if comment.get('reply_to_id') is not None:
            reply = ' 回复 ' + (comment.get('to_name') or authors.get(comment['reply_to_id']) or '未知对象')
        yield 'text', f'{author}{reply}：{comment.get("text") or ""}'


def tex_escape(text):
    mapping = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '$': r'\$',
               '&': r'\&', '#': r'\#', '%': r'\%', '_': r'\_',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(char, char) for char in text)


def write_exclusive(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError('Existing export differs; refusing overwrite')
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)
    return True


def render_tex(items, path):
    parts = [r'\documentclass[UTF8,fontset=fandol]{ctexart}', r'\usepackage[a4paper,margin=25mm]{geometry}',
             r'\usepackage{graphicx}', r'\setlength{\parindent}{0pt}', r'\begin{document}']
    for kind, value in items:
        if kind == 'image':
            data, _ = value
            name = hashlib.sha256(data).hexdigest() + '.png'
            write_exclusive(path.parent / 'assets' / name, data)
            parts.append(r'\par\begin{center}\includegraphics[width=\linewidth,height=0.78\textheight,keepaspectratio]{assets/' + name + r'}\end{center}\par')
        elif kind == 'heading':
            parts.append(r'\section*{' + tex_escape(value) + '}')
        else:
            parts.append('\n\n'.join(tex_escape(line) + r'\par' for line in str(value).splitlines()))
    return ('\n\n'.join(parts) + '\n\\end{document}\n').encode('utf-8')


def render_docx(items):
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Pt(595.28), Pt(841.89)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Pt(72)
    for name in ('Normal', 'Heading 1'):
        style = doc.styles[name]
        style.font.name = 'SimSun'
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'SimSun')
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].paragraph_format.space_after = Pt(8)
    doc.core_properties.author = 'Hope Archive'
    doc.core_properties.last_modified_by = 'Hope Archive'
    doc.core_properties.created = doc.core_properties.modified = datetime(2000, 1, 1)
    for kind, value in items:
        if kind == 'image':
            data, (width, height) = value
            doc.add_picture(BytesIO(data), width=Pt(width), height=Pt(height))
        elif kind == 'heading':
            doc.add_heading(value, level=1)
        else:
            doc.add_paragraph(str(value))
    result = BytesIO()
    doc.save(result)
    # Stable timestamps make repeated identical exports safely skippable.
    stable = BytesIO()
    with zipfile.ZipFile(result) as source, zipfile.ZipFile(stable, 'w', zipfile.ZIP_DEFLATED) as target:
        for name in sorted(source.namelist()):
            entry = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, source.read(name))
    return stable.getvalue()


def render_pdf(items):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Image as PDFImage, Spacer
    font = 'HopeChinese'
    if font not in pdfmetrics.getRegisteredFontNames():
        system_font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simsun.ttc'
        if system_font.is_file():
            pdfmetrics.registerFont(TTFont(font, str(system_font), subfontIndex=0))
        else:
            font = 'STSong-Light'
            pdfmetrics.registerFont(UnicodeCIDFont(font))
    regular = ParagraphStyle('Diary', fontName=font, fontSize=11, leading=17, spaceAfter=9, wordWrap='CJK')
    heading = ParagraphStyle('Heading', parent=regular, fontSize=16, leading=23, spaceAfter=14)
    story = []
    for kind, value in items:
        if kind == 'image':
            data, (width, height) = value
            story.extend([PDFImage(BytesIO(data), width=width, height=height), Spacer(1, 10)])
        else:
            story.append(Paragraph(escape(str(value)).replace('\n', '<br/>'), heading if kind == 'heading' else regular))
    target = BytesIO()
    SimpleDocTemplate(target, pagesize=(595.28, 841.89), rightMargin=72, leftMargin=72,
                      topMargin=72, bottomMargin=72, invariant=1, title='Hope Archive', author='Hope Archive').build(story)
    return target.getvalue()


def export_document(document, manifest, archive, output_dir, format='markdown'):
    format = ExportFormat(format)
    archive, output_dir = Path(archive).resolve(), Path(output_dir).resolve()
    if format == ExportFormat.MARKDOWN:
        return export_diaries(document, manifest, archive, output_dir)
    stats = dict(entries=len(document['diaries']), generated=0, skipped=0, failed=0)
    seen = set()
    for diary in document['diaries']:
        try:
            path = output_dir / diary_path(diary).with_suffix('.' + format.value)
            if path in seen:
                raise ValueError('Duplicate diary')
            seen.add(path)
            items = list(blocks(diary, manifest, archive))
            data = render_tex(items, path) if format == ExportFormat.TEX else render_pdf(items) if format == ExportFormat.PDF else render_docx(items)
            stats['generated' if write_exclusive(path, data) else 'skipped'] += 1
        except (OSError, ValueError, TypeError):
            stats['failed'] += 1  # Never log diary content or private paths.
    return stats
