from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas, binaries, hiddenimports = collect_all('rapidocr')
a = Analysis([str(root / 'packaging/ocr_entry.py')], pathex=[str(root / 'src')],
    binaries=binaries, datas=datas,
    hiddenimports=hiddenimports + ['rapidocr.inference_engine.onnxruntime', 'onnxruntime'],
    excludes=['tkinter', 'torch', 'paddle', 'openvino'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='hope-archive-ocr',
          debug=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ocr-runtime')
