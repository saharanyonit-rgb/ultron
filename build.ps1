# JARVIS Desktop Application - PowerShell Build Script
#
# This script builds the JARVIS desktop application using PyInstaller.
#
# Prerequisites:
#   - Python 3.12+ in .venv
#   - pip install pyinstaller pystray pillow
#
# Usage:
#   .\build.ps1              Build release
#   .\build.ps1 -Debug       Build debug version
#   .\build.ps1 -Clean       Clean only

param(
    [switch]$Debug,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  JARVIS Desktop Application - Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/7] Checking Python environment..." -ForegroundColor Yellow
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "ERROR: Python virtual environment not found" -ForegroundColor Red
    Write-Host "Please create one: py -3.12 -m venv .venv" -ForegroundColor Red
    exit 1
}

$PYTHON = ".venv\Scripts\python.exe"
& $PYTHON --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not working correctly" -ForegroundColor Red
    exit 1
}
Write-Host "       Python: OK" -ForegroundColor Green

# Check PyInstaller
Write-Host "[2/7] Checking PyInstaller..." -ForegroundColor Yellow
& $PYTHON -m PyInstaller --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "       Installing PyInstaller..." -ForegroundColor Yellow
    & $PYTHON -m pip install pyinstaller pystray pillow --quiet
}
Write-Host "       PyInstaller: OK" -ForegroundColor Green

# Clean previous builds
if ($Clean) {
    Write-Host "[3/7] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    Write-Host "       Cleaned: OK" -ForegroundColor Green
    Write-Host ""
    Write-Host "Clean complete." -ForegroundColor Green
    exit 0
}

Write-Host "[3/7] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Write-Host "       Cleaned: OK" -ForegroundColor Green

# Build JARVIS
Write-Host "[4/7] Building JARVIS executable..." -ForegroundColor Yellow
Write-Host "       This may take a few minutes..." -ForegroundColor Gray

$pyinstallerArgs = @(
    "-m", "PyInstaller",
    "jarvis.spec",
    "--clean",
    "--noconfirm",
    "--distpath", "dist",
    "--workpath", "build"
)

if ($Debug) {
    Write-Host "       Building DEBUG version..." -ForegroundColor Yellow
    $pyinstallerArgs += "--log-level", "DEBUG"
} else {
    Write-Host "       Building RELEASE version..." -ForegroundColor Yellow
}

& $PYTHON @pyinstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    exit 1
}
Write-Host "       Build: OK" -ForegroundColor Green

# Build single-file standalone executable
Write-Host "[5/7] Building single-file standalone..." -ForegroundColor Yellow
Write-Host "       This may take a few minutes..." -ForegroundColor Gray

$onefileArgs = @(
    "-m", "PyInstaller",
    "jarvis_onefile.spec",
    "--clean",
    "--noconfirm",
    "--distpath", "dist",
    "--workpath", "build"
)

if ($Debug) {
    $onefileArgs += "--log-level", "DEBUG"
}

& $PYTHON @onefileArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Single-file build failed" -ForegroundColor Red
    exit 1
}
Write-Host "       Standalone build: OK" -ForegroundColor Green

# Verify output
Write-Host "[6/7] Verifying build output..." -ForegroundColor Yellow
if (-not (Test-Path "dist\JARVIS\JARVIS.exe")) {
    Write-Host "ERROR: JARVIS.exe not found in dist\JARVIS\" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "dist\JARVIS.exe")) {
    Write-Host "ERROR: Standalone JARVIS.exe not found in dist\" -ForegroundColor Red
    exit 1
}
Write-Host "       Build output: OK" -ForegroundColor Green

# Create release directory
Write-Host "[7/7] Creating release directory..." -ForegroundColor Yellow
if (Test-Path "release") { Remove-Item -Recurse -Force "release" }
New-Item -ItemType Directory -Path "release" | Out-Null
Copy-Item "dist\JARVIS.exe" "release\JARVIS.exe" -Force
if (Test-Path "README.md") { Copy-Item "README.md" "release\README.md" -Force }
if (Test-Path "LICENSE") { Copy-Item "LICENSE" "release\LICENSE" -Force }
if (Test-Path "BUILD.md") { Copy-Item "BUILD.md" "release\BUILD.md" -Force }
if (Test-Path "ARCHITECTURE.md") { Copy-Item "ARCHITECTURE.md" "release\ARCHITECTURE.md" -Force }
if (Test-Path "RELEASE_NOTES.md") { Copy-Item "RELEASE_NOTES.md" "release\RELEASE_NOTES.md" -Force }

# Create release zip
Compress-Archive -Path "dist\JARVIS\*" -DestinationPath "release\JARVIS-Portable.zip" -Force
Write-Host "       Release directory: OK" -ForegroundColor Green

# Done
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Output:" -ForegroundColor Cyan
Write-Host "    dist\JARVIS\            (onedir distribution - fast startup)" -ForegroundColor White
Write-Host "    dist\JARVIS.exe         (standalone single-file executable)" -ForegroundColor White
Write-Host "    release\JARVIS.exe      (standalone for distribution)" -ForegroundColor White
Write-Host "    release\JARVIS-Portable.zip (portable onedir package)" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
