"""Offline frozen-worker smoke using only the repository's synthetic fixtures."""
import base64
import json
from pathlib import Path
import subprocess
import sys
from io import BytesIO
from PIL import Image

root = Path(__file__).resolve().parents[1]
fixtures = root/'tests/fixtures/ocr'
names = ['01_chinese_clear.png','02_english_clear.png','03_mixed_technical.png','16_blank.png']
images = [{'name':name,'data':base64.b64encode((fixtures/name).read_bytes()).decode()} for name in names]
for format in ('JPEG','WEBP'):
    data=BytesIO()
    with Image.open(fixtures/names[0]) as image: image.save(data,format=format)
    name='synthetic.'+format.lower()
    names.append(name)
    images.append({'name':name,'data':base64.b64encode(data.getvalue()).decode()})
command = [str(Path(sys.argv[1]).resolve())]
result = subprocess.run(command, input=json.dumps({'images':images}).encode(),
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=90,
    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
assert result.returncode == 0, 'Packaged OCR failed'
data = json.loads(result.stdout)
assert [p['name'] for p in data['pages']] == names
assert all(p['state']=='success' for p in data['pages'][:3])
assert '图书馆' in data['pages'][0]['text'] and 'Python' in data['pages'][2]['text']
assert data['pages'][3]['state']=='no-text'
assert all(p['state']=='success' for p in data['pages'][4:])
assert all((Path(command[0]).parent/'_internal/rapidocr/models'/name).is_file() for name in
    ('PP-OCRv6_det_small.onnx','PP-OCRv6_rec_small.onnx','ch_ppocr_mobile_v2.0_cls_mobile.onnx'))
print('PASS: bundled OCR models, Chinese/English/mixed input, PNG/JPEG/WEBP, ordered pages, no-text and worker exit')
