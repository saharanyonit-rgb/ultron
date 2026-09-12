@echo off
REM ============================================
REM JARVIS Desktop Application - Build Script
REM ============================================
REM
REM This script builds the JARVIS desktop application
REM using PyInstaller. Run this from the project root.
REM
REM Prerequisites:
REM   - Python 3.12+ in .venv
REM   - pip install pyinstaller pystray pillow
REM
REM Usage:
REM   build.bat           Build release
REM   build.bat debug     Build debug version
REM
REM ============================================

setlocal enabledelayedexpansion

echo.
echo ============================================
echo   JARVIS Desktop Application - Build Script
echo ============================================
echo.

REM Check Python
echo [1/7] Checking Python environment...
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found
    echo Please create one: py -3.12 -m venv .venv
    exit /b 1
)

set PYTHON=.venv\Scripts\python.exe
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not working correctly
    exit /b 1
)
echo       Python: OK

REM Check PyInstaller
echo [2/7] Checking PyInstaller...
%PYTHON% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo       Installing PyInstaller...
    %PYTHON% -m pip install pyinstaller pystray pillow --quiet
)
echo       PyInstaller: OK

REM Clean previous builds
echo [3/7] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo       Cleaned: OK

REM Build JARVIS
echo [4/7] Building JARVIS executable...
echo       This may take a few minutes...

if "%1"=="debug" (
    echo       Building DEBUG version...
    %PYTHON% -m PyInstaller jarvis.spec --clean --noconfirm --distpath dist --workpath build --log-level DEBUG
) else (
    echo       Building RELEASE version...
    %PYTHON% -m PyInstaller jarvis.spec --clean --noconfirm --distpath dist --workpath build
)

if errorlevel 1 (
    echo ERROR: Build failed
    exit /b 1
)
echo       Build: OK

REM Build single-file executable
echo [5/7] Building single-file standalone executable...
echo       This may take a few minutes...

if "%1"=="debug" (
    %PYTHON% -m PyInstaller jarvis_onefile.spec --clean --noconfirm --distpath dist --workpath build --log-level DEBUG
) else (
    %PYTHON% -m PyInstaller jarvis_onefile.spec --clean --noconfirm --distpath dist --workpath build
)

if errorlevel 1 (
    echo ERROR: Single-file build failed
    exit /b 1
)
echo       Standalone build: OK

REM Verify output
echo [6/7] Verifying build output...
if not exist "dist\JARVIS\JARVIS.exe" (
    echo ERROR: JARVIS.exe not found in dist\JARVIS\
    exit /b 1
)
if not exist "dist\JARVIS.exe" (
    echo ERROR: Standalone JARVIS.exe not found in dist\
    exit /b 1
)
echo       Build output: OK

REM Create release directory
echo [7/7] Creating release directory...
if exist "release" rmdir /s /q "release"
mkdir release
copy "dist\JARVIS.exe" "release\JARVIS.exe" >nul
copy "README.md" "release\README.md" >nul 2>&1
copy "LICENSE" "release\LICENSE" >nul 2>&1
copy "BUILD.md" "release\BUILD.md" >nul 2>&1
copy "ARCHITECTURE.md" "release\ARCHITECTURE.md" >nul 2>&1
copy "RELEASE_NOTES.md" "release\RELEASE_NOTES.md" >nul 2>&1
powershell -Command "Compress-Archive -Path 'dist\JARVIS\*' -DestinationPath 'release\JARVIS-Portable.zip' -Force"
echo       Release directory: OK

REM Done
echo.
echo ============================================
echo   Build complete!
echo.
echo   Output:
echo     dist\JARVIS\            (onedir distribution - fast startup)
echo     dist\JARVIS.exe         (standalone single-file executable)
echo     release\JARVIS.exe      (standalone for distribution)
echo     release\JARVIS-Portable.zip (portable onedir package)
echo ============================================
echo.

endlocal
