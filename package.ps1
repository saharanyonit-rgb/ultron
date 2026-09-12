# JARVIS Release Packaging Script (PowerShell)

param(
    [switch]$Full   # Include installer (requires Inno Setup)
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  JARVIS Release Packaging" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check dist
Write-Host "[1/4] Checking build output..." -ForegroundColor Yellow
$onedir = Test-Path "dist\JARVIS\JARVIS.exe"
$onefile = Test-Path "dist\JARVIS.exe"
if (-not $onedir) {
    Write-Host "ERROR: one-dir build (dist\JARVIS\) not found. Run: PyInstaller jarvis.spec" -ForegroundColor Red
    exit 1
}
if (-not $onefile) {
    Write-Host "ERROR: one-file build (dist\JARVIS.exe) not found. Run: PyInstaller jarvis_onefile.spec" -ForegroundColor Red
    exit 1
}
Write-Host "       Build output: OK" -ForegroundColor Green

# Kill any running JARVIS instances so the archive is not locked
Get-Process -Name "JARVIS" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Create release directory
Write-Host "[2/4] Preparing release directory..." -ForegroundColor Yellow
if (Test-Path "release") { Remove-Item -Recurse -Force "release" }
New-Item -ItemType Directory -Path "release" | Out-Null
Write-Host "       Release directory: OK" -ForegroundColor Green

# Copy release artifacts (standalone single-file executable + portable onedir folder)
Write-Host "[3/4] Creating release artifacts..." -ForegroundColor Yellow
if (Test-Path "dist\JARVIS.exe") {
    Copy-Item "dist\JARVIS.exe" "release\JARVIS.exe" -Force
} else {
    Copy-Item "dist\JARVIS_standalone\JARVIS.exe" "release\JARVIS.exe" -Force
}
if (Test-Path "README.md") { Copy-Item "README.md" "release\README.md" -Force }
if (Test-Path "BUILD.md") { Copy-Item "BUILD.md" "release\BUILD.md" -Force }
if (Test-Path "ARCHITECTURE.md") { Copy-Item "ARCHITECTURE.md" "release\ARCHITECTURE.md" -Force }
if (Test-Path "RELEASE_NOTES.md") { Copy-Item "RELEASE_NOTES.md" "release\RELEASE_NOTES.md" -Force }
if (Test-Path "LICENSE") { Copy-Item "LICENSE" "release\LICENSE" -Force }
Write-Host "       Standalone executable: OK" -ForegroundColor Green

# Create portable zip (entire onedir folder, runnable without install)
Write-Host "       Creating portable zip..." -ForegroundColor Yellow
Compress-Archive -Path "dist\JARVIS\*" -DestinationPath "release\JARVIS-Portable.zip" -Force
Write-Host "       Portable zip: OK" -ForegroundColor Green

# Optional installer
if ($Full) {
    Write-Host "[4/4] Creating installer..." -ForegroundColor Yellow
    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        Write-Host "       ERROR: Inno Setup not found. Skipping installer." -ForegroundColor Red
    } else {
        & $iscc "installer\JARVIS.iss"
        if (Test-Path "installer\Output\JARVIS-Installer.exe") {
            Copy-Item "installer\Output\JARVIS-Installer.exe" "release\JARVIS-Installer.exe" -Force
            Write-Host "       Installer: OK" -ForegroundColor Green
        }
    }
} else {
    Write-Host "[4/4] Skipped installer (use -Full to include)" -ForegroundColor Yellow
}

# Done
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Release complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  release\" -ForegroundColor White
Write-Host "    JARVIS.exe              (standalone executable)" -ForegroundColor White
Write-Host "    JARVIS-Portable.zip     (portable package)" -ForegroundColor White
if ($Full) { Write-Host "    JARVIS-Installer.exe   (installer)" -ForegroundColor White }
Write-Host "    README.md" -ForegroundColor White
Write-Host "    RELEASE_NOTES.md" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""