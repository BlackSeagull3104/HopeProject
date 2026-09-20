"""Shared diary presentation with bounded, offline document renderers."""
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
                              resolve_media, person_name, export_diaries)


class ExportFormat(str, Enum):
    MARKDOWN = 'markdown'
    TEX = 'tex'
    PDF = 'pdf'
    DOCX = 'docx'
    TXT = 'txt'


def fit_image(width, height, max_width=450, max_height=600):
    if width <= 0 or height <= 0:
        raise ValueError('Invalid image dimensions')
    scale = min(max_width / width, max_height / height, 1)
    return width * scale, height * scale


def image_parts(path):
    """One oriented image, never slice a screenshot into oversized page fragments."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        data = BytesIO()
        image.save(data, format='PNG')
        yield data.getvalue(), image.size


def blocks(diary, manifest, archive):
    from .document import diary_blocks
    for kind, value in diary_blocks(diary):
        if kind in ('image', 'media'):
            media_kind, url = value
            local = resolve_media(url, manifest, archive)
            if kind == 'image' and local:
                try:
                    yield from (('image', part) for part in image_parts(local))
                except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
                    yield 'missing', '[本地媒体不可用]'
            else:
                yield 'missing' if not local else 'text', '[本地媒体不可用]' if not local else f'[{media_kind}：{local.name}]'
        elif kind == 'comment':
            comment, authors = value
            author = person_name(comment) or '作者未知'
            reply = ''
            if comment.get('reply_to_id') is not None:
                reply = ' 回复 ' + (comment.get('to_name') or authors.get(comment['reply_to_id']) or '未知对象')
            yield 'comment', f'{author}{reply}：{comment.get("text") or ""}'
        else:
            yield kind, value


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
             r'\usepackage{graphicx}', r'\setlength{\parindent}{0pt}', r'\setlength{\parskip}{9pt}', r'\begin{document}']
    pending=[]
    def flush():
        for row in pdf_image_rows(pending, available_width=453.54):
            pictures=[]
            for data,(width,height) in row:
                name=hashlib.sha256(data).hexdigest()+'.png'
                write_exclusive(path.parent/'assets'/name,data)
                pictures.append(r'\includegraphics[width='+f'{width:.3f}pt,height={height:.3f}pt'+r',keepaspectratio]{assets/'+name+'}')
            parts.append(r'\par\noindent\makebox[\linewidth][c]{'+r'\hspace{12pt}'.join(pictures)+r'}\par\vspace{12pt}')
        pending.clear()
    for kind, value in items:
        if kind == 'image':
            pending.append(value)
            continue
        flush()
        if kind == 'page':
            parts.append(r'\newpage')
        elif kind in ('heading', 'title', 'subheading'):
            parts.append((r'\section*{' if kind=='heading' else r'\subsection*{') + tex_escape(value) + '}')
        else:
            parts.append('\n\n'.join(tex_escape(line) + r'\par' for line in str(value).splitlines()))
    flush()
    return ('\n\n'.join(parts) + '\n\\end{document}\n').encode('utf-8')


def render_docx(items):
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Pt(595.28), Pt(841.89)
    section.top_margin = section.bottom_margin = Pt(54)
    section.left_margin = section.right_margin = Pt(56)
    for name in ('Normal', 'Heading 1', 'Heading 2'):
        style = doc.styles[name]
        style.font.name = 'SimSun'
        style.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), 'SimSun')
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].paragraph_format.line_spacing = Pt(17)
    doc.styles['Normal'].paragraph_format.space_after = Pt(8)
    doc.core_properties.author = 'Hope Archive'
    doc.core_properties.last_modified_by = 'Hope Archive'
    doc.core_properties.created = doc.core_properties.modified = datetime(2000, 1, 1)
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.shared import RGBColor
    for name,size in [('Heading 1',17),('Heading 2',13)]:
        doc.styles[name].font.size=Pt(size)
        doc.styles[name].font.color.rgb=RGBColor.from_string('222222')
    pending=[]
    def add_image(paragraph,data,size):
        paragraph.alignment=WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after=Pt(12)
        paragraph.add_run().add_picture(BytesIO(data),width=Pt(size[0]),height=Pt(size[1]))
    def flush():
        for row in pdf_image_rows(pending):
            if len(row)==1:
                add_image(doc.add_paragraph(),*row[0])
            else:
                table=doc.add_table(rows=1,cols=3)
                table.autofit=False
                widths=[(PDF_BODY_WIDTH-12)/2,12,(PDF_BODY_WIDTH-12)/2]
                for column,width in zip(table.columns,widths): column.width=Pt(width)
                for cell,width in zip(table.rows[0].cells,widths):
                    cell.width=Pt(width)
                    margins=OxmlElement('w:tcMar')
                    for side in ('top','left','bottom','right'):
                        edge=OxmlElement('w:'+side);edge.set(qn('w:w'),'0');edge.set(qn('w:type'),'dxa');margins.append(edge)
                    cell._tc.get_or_add_tcPr().append(margins)
                props=table.rows[0]._tr.get_or_add_trPr();props.append(OxmlElement('w:cantSplit'))
                for index,(data,size) in zip((0,2),row): add_image(table.cell(0,index).paragraphs[0],data,size)
        pending.clear()
    for kind, value in items:
        if kind=='image':
            pending.append(value)
            continue
        flush()
        if kind == 'page':
            doc.add_page_break()
        elif kind in ('heading', 'title', 'subheading'):
            doc.add_heading(value, level=1 if kind == 'heading' else 2)
        else:
            paragraph=doc.add_paragraph(str(value))
            if kind in ('comment','metadata','missing'):
                if kind=='comment': paragraph.paragraph_format.left_indent=Pt(12)
                for run in paragraph.runs:
                    run.font.size=Pt(9.5)
                    run.font.color.rgb=RGBColor.from_string('555555')
    flush()
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


from .image_layout import PDF_PAGE, PDF_MARGIN, PDF_BODY_WIDTH, PDF_IMAGE_GAP, image_rows as pdf_image_rows


def render_pdf(items):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Image as PDFImage, Spacer, PageBreak, Table, TableStyle
    font = 'HopeChinese'
    if font not in pdfmetrics.getRegisteredFontNames():
        system_font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simsun.ttc'
        if system_font.is_file():
            pdfmetrics.registerFont(TTFont(font, str(system_font), subfontIndex=0))
        else:
            font = 'STSong-Light'
            if font not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(UnicodeCIDFont(font))
    regular = ParagraphStyle('Diary', fontName=font, fontSize=10.5, leading=17, spaceAfter=9, wordWrap='CJK')
    styles = {
        'heading': ParagraphStyle('Date', parent=regular, fontSize=17, leading=23, spaceBefore=16, spaceAfter=10, keepWithNext=True),
        'title': ParagraphStyle('Title', parent=regular, fontSize=13, leading=19, spaceAfter=10, keepWithNext=True),
        'subheading': ParagraphStyle('Section', parent=regular, fontSize=11.5, leading=18, spaceBefore=10, keepWithNext=True),
        'metadata': ParagraphStyle('Metadata', parent=regular, fontSize=9, textColor=HexColor('#626262')),
        'comment': ParagraphStyle('Comment', parent=regular, fontSize=9.5, leading=15, leftIndent=12, textColor=HexColor('#555555')),
        'missing': ParagraphStyle('Missing', parent=regular, fontSize=9, textColor=HexColor('#666666')),
    }
    story, pending = [], []
    def flush_images():
        for row in pdf_image_rows(pending):
            images = [PDFImage(BytesIO(data), width=size[0], height=size[1], hAlign='CENTER') for data, size in row]
            if len(images) == 1:
                story.append(images[0])
            else:
                cell = (PDF_BODY_WIDTH - PDF_IMAGE_GAP) / 2
                table = Table([[images[0], '', images[1]]], colWidths=[cell, PDF_IMAGE_GAP, cell], hAlign='CENTER')
                table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('ALIGN',(0,0),(-1,-1),'CENTER'),
                    ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
                    ('TOPPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
                story.append(table)
            story.append(Spacer(1, PDF_IMAGE_GAP))
        pending.clear()
    for kind, value in items:
        if kind == 'image':
            pending.append(value)
            continue
        flush_images()
        if kind == 'page':
            story.append(PageBreak())
        else:
            # Paragraphs remain literal diary text; never interpret user HTML.
            text = str(value).replace(' ☀️', '') if kind == 'metadata' else str(value)
            paragraphs = text.split('\n\n') if kind in ('text', 'comment') else [text]
            for paragraph in paragraphs:
                if paragraph:
                    story.append(Paragraph(escape(paragraph).replace('\n', '<br/>'), styles.get(kind, regular)))
    flush_images()
    target = BytesIO()
    SimpleDocTemplate(target, pagesize=PDF_PAGE, rightMargin=PDF_MARGIN, leftMargin=PDF_MARGIN,
                      topMargin=54, bottomMargin=54, invariant=1, title='Hope Archive', author='Hope Archive').build(story)
    return target.getvalue()


def render_items(items, path, format):
    """Shared output renderers for diaries, opened capsules and editable OCR pages."""
    format = ExportFormat(format)
    if format == ExportFormat.TEX: return render_tex(items, path)
    if format == ExportFormat.PDF: return render_pdf(items)
    if format == ExportFormat.DOCX: return render_docx(items)
    return '\n\n'.join(('\f' if format == ExportFormat.TXT else '---') if kind == 'page'
        else ('# ' if kind == 'heading' and format == ExportFormat.MARKDOWN else '') + str(value)
        for kind, value in items if kind != 'image').encode('utf-8')


def export_pages(pages, output, format, title='识图文字'):
    import uuid
    if not isinstance(pages, list) or not 1 <= len(pages) <= 200:
        raise ValueError('没有可导出的页面。')
    items = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get('text'), str) or len(page['text']) > 500_000:
            raise ValueError('页面内容无效。')
        if index: items.append(('page', ''))
        items.extend([('heading', f'{title} · {index + 1}'), ('text', page['text'])])
    format = ExportFormat(format)
    suffix = 'md' if format == ExportFormat.MARKDOWN else format.value
    path = Path(output) / f'{title}_{datetime.now():%Y%m%d-%H%M%S}_{uuid.uuid4().hex[:10]}.{suffix}'
    path.parent.mkdir(parents=True, exist_ok=True)
    write_exclusive(path, render_items(items, path, format))
    return {'path': str(path), 'pages': len(pages)}


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
            data = render_items(items, path, format)
            stats['generated' if write_exclusive(path, data) else 'skipped'] += 1
        except (OSError, ValueError, TypeError):
            stats['failed'] += 1  # Never log diary content or private paths.
    return stats


def range_filename(nickname, begin, end, format):
    import re
    from .application import validate_date_range
    validate_date_range(begin, end)
    format = ExportFormat(format)
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', nickname or '').strip().rstrip('. ')
    # Numeric/phone-like nicknames are not used as public filenames.
    if not name or re.fullmatch(r'[+\d\s()_-]+', name) or name == 'Hope 用户':
        stem = 'Hope日记'
    else:
        stem = name[:80].rstrip('. ') + '的日记'
    suffix = 'md' if format == ExportFormat.MARKDOWN else format.value
    return f'{stem}_{begin}--{end}.{suffix}'


def export_range(document, manifest, archive, output_dir, format, nickname, begin, end):
    """User-facing combined export; archive's per-entry files remain unchanged."""
    from .export_markdown import render_diary
    format = ExportFormat(format)
    archive = Path(archive).resolve()
    path = Path(output_dir).resolve() / range_filename(nickname, begin, end, format)
    stats = dict(entries=len(document['diaries']), generated=0, skipped=0, failed=0)
    if not document['diaries']:
        return stats
    try:
        if format == ExportFormat.MARKDOWN:
            data = '\n---\n\n'.join(render_diary(d, manifest, archive, path) for d in document['diaries']).encode('utf-8')
        else:
            items = [block for d in document['diaries'] for block in blocks(d, manifest, archive)]
            data = render_items(items, path, format)
        stats['generated' if write_exclusive(path, data) else 'skipped'] = 1
    except (OSError, ValueError, TypeError):
        stats['failed'] = 1
    return stats
