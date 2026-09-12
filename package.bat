@echo off
REM ============================================
REM JARVIS Release Packaging Script
REM ============================================
REM
REM Creates the release artifacts:
REM   1. JARVIS.exe (standalone executable)
REM   2. JARVIS-Portable.zip (portable package)
REM   3. JARVIS-Installer.exe (Inno Setup installer, optional)
REM
REM Prerequisites:
REM   - PyInstaller build completed (dist/JARVIS/)
REM   - Inno Setup installed (for installer, optional)
REM
REM Usage:
REM   package.bat          Package release
REM   package.bat --full   Include installer (requires Inno Setup)
REM
REM ============================================

setlocal enabledelayedexpansion

echo.
echo ============================================
echo   JARVIS Release Packaging
echo ============================================
echo.

REM Check dist
echo [1/4] Checking build output...
if not exist "dist\JARVIS\JARVIS.exe" (
    echo ERROR: Build output not found. Run build.bat first.
    exit /b 1
)
echo       Build output: OK

REM Create release directory
echo [2/4] Preparing release directory...
if exist "release" rmdir /s /q "release"
mkdir "release"
echo       Release directory: OK

REM Copy standalone executable
echo [3/4] Creating release artifacts...
copy "dist\JARVIS\JARVIS.exe" "release\JARVIS.exe" >nul
copy "README.md" "release\README.md" >nul 2>&1
copy "ARCHITECTURE.md" "release\ARCHITECTURE.md" >nul 2>&1
copy "RELEASE_NOTES.md" "release\RELEASE_NOTES.md" >nul 2>&1
copy "LICENSE" "release\LICENSE" >nul 2>&1
echo       Standalone executable: OK

REM Create portable zip
powershell -Command "Compress-Archive -Path 'dist\\JARVIS\\*' -DestinationPath 'release\\JARVIS-Portable.zip' -Force"
if errorlevel 1 (
    echo WARNING: Could not create portable zip
) else (
    echo       Portable zip: OK
)

REM Optional: create installer
if "%1"=="--full" (
    echo [4/4] Creating installer...
    if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        echo ERROR: Inno Setup not found. Skipping installer.
    ) else (
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "installer\JARVIS.iss"
        if exist "installer\Output\JARVIS-Installer.exe" (
            copy "installer\Output\JARVIS-Installer.exe" "release\JARVIS-Installer.exe" >nul
            echo       Installer: OK
        ) else (
            echo WARNING: Installer build failed
        )
    )
) else (
    echo [4/4] Skipped installer (use --full to include)
)

REM Done
echo.
echo ============================================
echo   Release complete!
echo.
echo   release\
echo     JARVIS.exe              (standalone executable)
echo     JARVIS-Portable.zip     (portable package)
if "%1"=="--full" (
    echo     JARVIS-Installer.exe   (installer)
)
echo     README.md
echo     RELEASE_NOTES.md
echo ============================================
echo.

endlocal