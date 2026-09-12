# BUILD.md - Building JARVIS Desktop Application

This document explains how to build the JARVIS desktop application from source.

## Prerequisites

### Required

- **Python 3.12+** (check: `py -3.12 --version`)
- **Git** (check: `git --version`)
- **Windows 10/11**

### Install Development Dependencies

```powershell
# Create virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project + dev dependencies
pip install -e ".[dev]"

# Install build dependencies
pip install pyinstaller pystray pillow
```

## Quick Build

### Option 1: Build Script (Recommended)

```powershell
.\build.ps1
```

This runs the full build pipeline:

1. Validates Python environment
2. Installs/checks PyInstaller
3. Cleans previous builds
4. Builds JARVIS.exe with PyInstaller (onedir spec)
5. Builds standalone single-file executable (onefile spec)
6. Verifies output
7. Creates release directory with artifacts

### Option 2: Manual Build

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Generate icon (optional)
python generate_icon.py

# Build onedir distribution (fast startup; frontend served from _internal/frontend)
python -m PyInstaller jarvis.spec --clean --noconfirm --distpath dist --workpath build

# Build standalone single-file executable
python -m PyInstaller jarvis_onefile.spec --clean --noconfirm --distpath dist --workpath build

# Outputs:
#   dist\JARVIS\        (onedir - run dist\JARVIS\JARVIS.exe)
#   dist\JARVIS.exe     (single-file standalone)
```

### Option 3: Debug Build

```powershell
.\build.ps1 -Debug
```

Or:

```powershell
.\build.bat debug
```

This enables debug logging and verbose PyInstaller output.

## Build Output

```
dist/
├── JARVIS/                  # Onedir distribution (fast startup)
│   ├── JARVIS.exe           # Main executable
│   ├── *.dll                # Python runtime
│   └── _internal/           # Bundled packages + frontend/
│       └── frontend/        # Web interface files
└── JARVIS.exe               # Single-file standalone executable

release/                     # Created by package.ps1 / package.bat
├── JARVIS.exe               # Standalone single-file executable (self-contained)
├── JARVIS-Portable.zip      # Portable onedir package (unzip and run)
├── README.md
├── ARCHITECTURE.md
├── BUILD.md
├── RELEASE_NOTES.md
└── LICENSE
```

## Packaging (Release Distribution)

After building, run the packaging script to create the distributable artifacts:

```powershell
.\package.ps1        # Standalone exe + portable zip
.\package.ps1 -Full  # Also build the Inno Setup installer (requires Inno Setup 6)
```

```bat
package.bat          # Standalone exe + portable zip
package.bat --full   # Also build the installer
```

The installer script is `installer/JARVIS.iss` (Inno Setup 6). Run it standalone with:

```
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\JARVIS.iss
```

## Build Configuration

### jarvis.spec

The PyInstaller onedir spec file configures:

- **Entry point:** `desktop/main.py`
- **Frontend files:** Bundled into `_internal/frontend/`
- **ULTRON package:** Full Python package bundled
- **Hidden imports:** All ULTRON modules explicitly listed
- **Excludes:** Unnecessary packages (pytest, numpy, IPython, GUI toolkits, etc.)
- **Icon:** `assets/icons/jarvis.ico`
- **Console:** Disabled (no terminal window)

### jarvis_onefile.spec

The single-file spec produces `dist\JARVIS.exe`. Same configuration as `jarvis.spec`
but bundles everything into one self-contained executable (68.5 MB, extracts to a
temp directory at each launch). Note: the onefile executable spawns a child process;
kill the process tree (`taskkill /PID <pid> /T /F`) rather than a single process.

### Customizing the Build

To modify what gets bundled, edit both spec files equally:

- **Add files:** Add to `datas` list
- **Add modules:** Add to `hiddenimports` list
- **Remove modules:** Add to `excludes` list
- **Change icon:** Update the `icon` path

## Development Mode

For development without building:

```powershell
# Terminal mode
.\.venv\Scripts\python -m ultron

# Web mode
.\.venv\Scripts\python -m ultron --web

# Desktop mode (system tray + browser)
.\.venv\Scripts\python -m desktop
```

## Troubleshooting

### Build Fails with "Module not found"

Add the missing module to `hiddenimports` in the spec file (both `jarvis.spec` and `jarvis_onefile.spec`).

### Build is Slow

PyInstaller analyzes all imports. First build takes 2-5 minutes. Subsequent builds with cached dependencies are faster.

### Missing Frontend Files

Ensure `frontend/` directory exists and contains `index.html`, `css/`, and `js/`.

### Icon Not Found

Run `python generate_icon.py` to create the icon, or remove the `icon=` line from `jarvis.spec`.

### Antivirus Flags the Executable

Some antivirus software flags PyInstaller executables. This is a false positive. You can:

1. Add an exclusion in your antivirus
2. Code-sign the executable (requires a certificate)
3. Submit the file for analysis to your antivirus vendor
