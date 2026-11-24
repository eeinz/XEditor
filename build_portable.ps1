# Build a portable, non-onefile XEditor directory and zip it.
# This avoids the temporary Qt DLL extraction that some antivirus tools lock.
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path "assets\xeditor.ico")) {
    throw "Missing assets\xeditor.ico"
}
if (-not (Test-Path "packaging\version_info.txt")) {
    throw "Missing packaging\version_info.txt"
}

New-Item -ItemType Directory -Force -Path "build-portable" | Out-Null

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name XEditor `
    --icon "assets\xeditor.ico" `
    --version-file "packaging\version_info.txt" `
    --collect-submodules markdown `
    --collect-submodules xeditor `
    --distpath "dist\portable" `
    --workpath "build-portable" `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

$folder = Join-Path $PSScriptRoot "dist\portable\XEditor"
$exe = Join-Path $folder "XEditor.exe"
if (-not (Test-Path $exe)) {
    throw "Portable executable was not created: $exe"
}

Copy-Item -Force "packaging\portable_readme.txt" (Join-Path $folder "README.txt")

$zip = Join-Path $PSScriptRoot "dist\XEditor-1.0.4-portable.zip"
if (Test-Path $zip) {
    Remove-Item -Force $zip
}
$zipCreated = $false
for ($attempt = 1; $attempt -le 6; $attempt++) {
    try {
        Compress-Archive -Path $folder -DestinationPath $zip -CompressionLevel Optimal -ErrorAction Stop
        $zipCreated = $true
        break
    } catch {
        if ($attempt -eq 6) {
            throw "Could not create portable zip after $attempt attempts: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 2
    }
}
if (-not $zipCreated) {
    throw "Portable zip was not created."
}

Write-Host ""
Write-Host "Portable build complete:" -ForegroundColor Green
Write-Host "  $exe"
Write-Host "  $zip"
Write-Host "  Size: $([math]::Round((Get-Item $exe).Length / 1MB, 1)) MB (exe only)"
