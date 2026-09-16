"""Collect exact installed distribution license files into the local OCR payload."""
from importlib import metadata
import json
from pathlib import Path
import shutil
import sys

destination = Path(sys.argv[1]) / 'THIRD_PARTY_NOTICES'
destination.mkdir(parents=True, exist_ok=True)
names = ['rapidocr','onnxruntime','opencv-python','numpy','shapely','pyclipper','omegaconf',
         'antlr4-python3-runtime','PyYAML','requests','Pillow','protobuf','flatbuffers','tqdm',
         'colorlog','six','packaging','colorama','certifi','charset_normalizer','idna','urllib3']
inventory = []
for name in names:
    dist = metadata.distribution(name)
    licenses = []
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license','copying','notice')):
            source = Path(dist.locate_file(file))
            if source.is_file() and source.suffix.lower() not in ('.py','.pyc','.pyd'):
                target = destination / name / str(file).replace('../','').replace('..\\','')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                licenses.append(str(target.relative_to(destination)))
    inventory.append({'distribution': name, 'version':dist.version,
        'license':dist.metadata.get('License-Expression') or dist.metadata.get('License'), 'notices':licenses})
(destination/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print('Collected OCR third-party notices:', len(inventory), 'distributions')
