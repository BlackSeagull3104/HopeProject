param()
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
# Explicit separate build: never invoked by build_windows.ps1.
# Install requirements-runtime.txt and packaging/requirements.txt first.
Push-Location $root
try {
    & $python -m PyInstaller --noconfirm --distpath dist/components --workpath build/runtime packaging/ocr.spec
    if ($LASTEXITCODE -ne 0) { throw 'Runtime build failed' }
    & $python -B scripts/collect_ocr_notices.py dist/components/ocr-runtime
    if ($LASTEXITCODE -ne 0) { throw 'Runtime notices collection failed' }
    & $python -B -X utf8 scripts/smoke_ocr.py dist/components/ocr-runtime/hope-archive-ocr.exe
    if ($LASTEXITCODE -ne 0) { throw 'Runtime OCR verification failed' }
    Write-Output 'Runtime built separately. Audit it and test semantic inference before producing trusted release metadata.'
} finally { Pop-Location }
