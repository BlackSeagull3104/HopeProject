"""One offline OCR batch per process. No Hope/AI dependencies or disk image cache."""
import base64
from io import BytesIO
import json
from pathlib import Path
import socket
import sys
import time


def deny_network(*args, **kwargs):
    raise RuntimeError('OCR network access is disabled')


def main():
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    started = time.perf_counter()
    import rapidocr
    import onnxruntime
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    cv2.setNumThreads(4)
    onnxruntime.disable_telemetry_events()
    models = Path(rapidocr.__file__).resolve().parent / 'models'
    names = ('PP-OCRv6_det_small.onnx', 'ch_ppocr_mobile_v2.0_cls_mobile.onnx', 'PP-OCRv6_rec_small.onnx')
    if not all((models / name).is_file() for name in names):
        raise RuntimeError('Bundled OCR models missing')
    payload = json.loads(sys.stdin.buffer.read(64 * 1024 * 1024 + 1))
    engine = rapidocr.RapidOCR(params={
        'Global.log_level': 'critical',
        'EngineConfig.onnxruntime.intra_op_num_threads': 4,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        **{key + '.model_path': str(models / name) for key, name in zip(('Det', 'Cls', 'Rec'), names)},
    })
    ready = time.perf_counter()
    pages = []
    for index, item in enumerate(payload['images']):
        page = {'index': index, 'name': item['name'], 'text': '', 'state': 'failed'}
        try:
            raw = base64.b64decode(item['data'], validate=True)
            with Image.open(BytesIO(raw)) as image:
                if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width * image.height > 20_000_000:
                    raise ValueError()
                pixels = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))[:, :, ::-1].copy()
            begin = time.perf_counter()
            result = engine(pixels)
            page.update(text='\n'.join(result.txts or []), seconds=time.perf_counter() - begin)
            page['state'] = 'success' if page['text'].strip() else 'no-text'
        except Exception:
            page['error'] = '无法识别此图片，请检查格式、文件完整性和图片尺寸。'
        pages.append(page)
    print(json.dumps({'pages': pages, 'initializationSeconds': ready - started}, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Native/model errors never echo image data, paths or provider information.
        sys.exit(1)
