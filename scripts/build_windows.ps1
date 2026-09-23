param([switch]$BackendOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .venv and install requirements.txt and packaging/requirements.txt first.' }
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'
if (Test-Path -LiteralPath $cargoBin) { $env:PATH = "$cargoBin;$env:PATH" }
Push-Location $root
try {
    & $python scripts/generate_icons.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon conversion failed' }
    & $python -m PyInstaller --noconfirm --distpath dist/backend --workpath build/ocr packaging/ocr.spec
    if ($LASTEXITCODE -ne 0) { throw 'OCR worker build failed' }
    & $python -B scripts/collect_ocr_notices.py dist/backend/ocr-runtime
    if ($LASTEXITCODE -ne 0) { throw 'OCR notices collection failed' }
    & $python -B -X utf8 scripts/smoke_ocr.py dist/backend/ocr-runtime/hope-archive-ocr.exe
    if ($LASTEXITCODE -ne 0) { throw 'Frozen OCR smoke test failed' }
    & $python -m PyInstaller --noconfirm --distpath dist/backend --workpath build/pyinstaller packaging/backend.spec
    if ($LASTEXITCODE -ne 0) { throw 'Backend build failed' }
    & $python -B -X utf8 scripts/smoke_backend.py dist/backend/hope-archive-backend.exe
    if ($LASTEXITCODE -ne 0) { throw 'Frozen backend smoke test failed' }
    $sidecars = Join-Path $root 'frontend\vite-app\src-tauri\binaries'
    New-Item -ItemType Directory -Force $sidecars | Out-Null
    # This first prototype explicitly targets Windows x64 / Python x64.
    Copy-Item -LiteralPath 'dist/backend/hope-archive-backend.exe' -Destination (Join-Path $sidecars 'hope-archive-backend-x86_64-pc-windows-msvc.exe')
    Copy-Item -LiteralPath 'dist/backend/ocr-runtime' -Destination $sidecars -Recurse -Force
    if ($BackendOnly) { return }
    if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'Rust/Cargo is missing. Install Rust MSVC and Microsoft C++ Build Tools.' }
    Push-Location frontend/vite-app
    try {
        npm run tauri -- build --bundles nsis --target x86_64-pc-windows-msvc
        if ($LASTEXITCODE -ne 0) { throw 'Tauri build failed' }
    } finally { Pop-Location }
    $portable = Join-Path $root 'dist\windows\Hope Archive'
    New-Item -ItemType Directory -Force $portable | Out-Null
    Copy-Item -LiteralPath 'frontend/vite-app/src-tauri/target/x86_64-pc-windows-msvc/release/hope-archive.exe' -Destination (Join-Path $portable 'Hope Archive.exe')
    Copy-Item -LiteralPath 'dist/backend/hope-archive-backend.exe' -Destination $portable
    Copy-Item -LiteralPath 'dist/backend/ocr-runtime' -Destination $portable -Recurse -Force
    & $python scripts/verify_executable_icon.py (Join-Path $portable 'Hope Archive.exe')
    if ($LASTEXITCODE -ne 0) { throw 'Executable icon verification failed' }
    $version = (Get-Content frontend/vite-app/src-tauri/tauri.conf.json -Raw | ConvertFrom-Json).version
    $installer = "frontend/vite-app/src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/Hope Archive_${version}_x64-setup.exe"
    if (-not (Test-Path -LiteralPath $installer)) { throw 'Installer missing' }
    New-Item -ItemType Directory -Force dist/releases | Out-Null
    $release = "dist/releases/HopeArchive-${version}-ai-v3-dev-Setup.exe"
    Copy-Item -LiteralPath $installer -Destination $release
    Write-Output "Installer: $release"
    Write-Output "Portable application: $portable"
} finally { Pop-Location }
