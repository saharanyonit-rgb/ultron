from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = [
    "desktop",
    "desktop.config",
    "desktop.server",
    "desktop.tray",
    "desktop.notifications",
    "desktop.startup",
    "desktop.main",
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
    ["ultron_desktop_entry.py"],
    pathex=["."],
    binaries=[],
    datas=[("frontend", "frontend")],
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
    icon=["assets/icons/jarvis.ico"],
)