import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Project root
ROOT = os.path.dirname(os.path.abspath(SPEC))

hiddenimports = [
    "desktop",
    "desktop.config",
    "desktop.server",
    "desktop.tray",
    "desktop.notifications",
    "desktop.startup",
    "desktop.window",
    "desktop.main",
    # Native UI host (WebView2 on Windows)
    "webview",
    "webview.guilib",
    "webview.util",
    "webview.http",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "clr_loader",
]

for package in [
    "ultron",
    "bsp",
    "group_agent",
    "utils",
    "planners",
    "providers",
]:
    hiddenimports += collect_submodules(package)

a = Analysis(
    [os.path.join(ROOT, "scripts", "ultron_desktop_entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Include the frontend files (index.html, css, js, vendor/three)
        (os.path.join(ROOT, "frontend"), "frontend"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "black", "ruff", "IPython", "jupyter", "matplotlib", "tkinter", "PyQt5", "PySide2"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[os.path.join(ROOT, "assets", "icons", "jarvis.ico")] if os.path.exists(os.path.join(ROOT, "assets", "icons", "jarvis.ico")) else None,
)