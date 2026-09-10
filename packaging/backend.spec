from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'packaging/backend_entry.py')],
    pathex=[str(root / 'src')],
    binaries=[], datas=[], hiddenimports=[],
    excludes=['tkinter', 'tkcalendar', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='hope-archive-backend', debug=False, strip=False, upx=False,
    console=True,
    icon=str(root / 'frontend/vite-app/src-tauri/icons/icon.ico'),
)
