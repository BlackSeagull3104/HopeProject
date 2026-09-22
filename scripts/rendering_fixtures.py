"""Deterministic synthetic renderer QA; never reads application/user data."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from hope_archive.export_documents import blocks, render_items
from hope_archive.export_markdown import render_diary
from hope_archive.media import media_key


def fixtures(root):
    root = Path(root)
    source = root / 'synthetic_media'
    source.mkdir(parents=True, exist_ok=True)
    manifest = {'media': {}}
    shapes = {'landscape': (1200, 675), 'square': (900, 900),
              'portrait': (720, 1280), 'long': (720, 7200)}
    for name, size in shapes.items():
        for index in range(4):
            filename = f'{name}-{index}.png'
            image = Image.new('RGB', size, ('#dce9ef', '#e8e1d4', '#dfe8db', '#e8dfe9')[index])
            draw = ImageDraw.Draw(image)
            for y in range(24, size[1] - 24, 64):
                draw.text((24, y), f'SYNTHETIC {name.upper()} {index + 1} / row {y // 64 + 1}', fill='#263544', font_size=24)
                draw.line((24, y + 36, size[0] - 24, y + 36), fill='#8297a3', width=2)
            image.save(source / filename)
            manifest['media'][media_key('https://fixture.invalid/' + filename)] = {
                'status': 'downloaded', 'local_path': filename}

    def picture(*names):
        return {'kind': 'image', 'media': [{'url': 'https://fixture.invalid/' + name + '.png'} for name in names]}

    zh = '这是完全合成的日记段落，用于检查中文排版、标点和段落间距。'
    en = 'This synthetic paragraph checks readable type, punctuation, line wrapping and spacing.'
    cases = [
        ('01-text-only', [{'text': 'Synthetic diary text.'}]),
        ('02-chinese', [{'text': zh + '\n\n' + zh * 3}]),
        ('03-english', [{'text': en + '\n\n' + en * 3}]),
        ('04-mixed', [{'text': zh + ' English 2026，PDF / DOCX。\n\n' + en + ' 中文续写。'}]),
        ('05-short', [{'text': '短段落。'}]),
        ('06-long-paragraph', [{'text': (zh + en) * 18}]),
        ('07-landscape', [picture('landscape-0')]),
        ('08-square', [picture('square-0')]),
        ('09-portrait', [picture('portrait-0')]),
        ('10-long-screenshot', [picture('long-0')]),
        ('11-portrait-pair', [picture('portrait-0', 'portrait-1')]),
        ('12-square-pair', [picture('square-0', 'square-1')]),
        ('13-incompatible', [picture('landscape-0', 'long-0')]),
        ('14-three-images', [picture('square-0', 'square-1', 'square-2')]),
        ('15-four-images', [picture('portrait-0', 'portrait-1', 'portrait-2', 'portrait-3')]),
        ('16-image-text-image', [picture('square-0'), {'text': zh + '\n\n' + en}, picture('portrait-0')]),
        ('17-comments', [{'text': zh}]),
        ('18-metadata', [{'text': zh}]),
        ('19-multiple-entries', [{'text': zh}, picture('landscape-0')]),
        ('20-page-boundaries', [{'text': '\n\n'.join(f'{i + 1}. {zh} {en}' for i in range(24))}, picture('portrait-0', 'portrait-1'), {'text': 'FINAL CONTENT 最后内容。'}]),
    ]
    for number, (name, content) in enumerate(cases, 1):
        diary = {'id': number, 'note_date': '2026-01-02', 'title': '合成日记 Synthetic diary', 'content': content}
        if number == 17:
            diary['comments'] = [{'items': [
                {'id': 1, 'from_name': '示例作者', 'text': zh + '\n\n' + en},
                {'id': 2, 'from_name': 'Example reader', 'reply_to_id': 1, 'text': '合成回复 Synthetic reply.'}]}]
        if number == 18:
            diary.update(emotion={'identity': 'emotion_ha'}, weather={'identity': 'weather_qing'})
        entries = [diary]
        if number == 19:
            last = deepcopy(diary)
            last.update(id=100, note_date='2026-01-03', title='最终篇 Final entry', content=[{'text': en}])
            entries.append(last)
        yield name, entries, manifest, source


def generate(root):
    root = Path(root)
    for name, entries, manifest, source in fixtures(root):
        output = root / name
        output.mkdir(parents=True, exist_ok=True)
        (output / 'fixture.md').write_text('\n---\n\n'.join(
            render_diary(entry, manifest, source, output / 'fixture.md') for entry in entries), encoding='utf-8')
        items = []
        for entry in entries:
            if items:
                items.append(('separator', ''))
            items.extend(blocks(entry, manifest, source))
        for format in ('pdf', 'docx', 'tex'):
            path = output / ('fixture.' + format)
            path.write_bytes(render_items(items, path, format))
    (root / 'README.md').write_text(
        '# Synthetic rendering QA\n\nAll 20 cases are generated without user data. Each case uses identical normalized input across MD/PDF/DOCX/TeX. '
        'Media files are labelled synthetic. Open fixture.md in the reference reader and compare fixture.pdf and fixture.docx. '
        'Keep assets beside each exported file when moving a case.\n\n'
        'Compile TeX using `lualatex fixture.tex` from its case directory. No TeX runtime is bundled with the application.\n', encoding='utf-8')
    print(json.dumps({'cases': 20, 'formats': ['md', 'pdf', 'docx', 'tex']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    generate(parser.parse_args().output)
