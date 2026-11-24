# Build a single-file, windowed XEditor executable.
# Requires: Python 3.10+, requirements.txt, PyInstaller.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path "assets\xeditor.ico")) {
    throw "Missing assets\xeditor.ico"
}
if (-not (Test-Path "packaging\version_info.txt")) {
    throw "Missing packaging\version_info.txt"
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name XEditor `
    --icon "assets\xeditor.ico" `
    --version-file "packaging\version_info.txt" `
    --collect-submodules markdown `
    --collect-submodules xeditor `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$exe = Join-Path $PSScriptRoot "dist\XEditor.exe"
Write-Host ""
Write-Host "Build complete: $exe" -ForegroundColor Green
if (Test-Path $exe) {
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "Size: $size MB"
}
