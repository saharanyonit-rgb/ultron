"""Windows startup integration.

Provides functions to register/unregister JARVIS to start with Windows.
Uses the Windows Startup folder (not registry) for safety.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.desktop.startup")

STARTUP_FOLDER_ENV = "APPDATA"
STARTUP_RELATIVE = r"Microsoft\Windows\Start Menu\Programs\Startup"
SHORTCUT_NAME = "JARVIS.lnk"


def _get_startup_folder() -> Optional[Path]:
    """Get the Windows Startup folder."""
    appdata = os.environ.get(STARTUP_FOLDER_ENV)
    if not appdata:
        return None
    startup = Path(appdata) / STARTUP_RELATIVE
    if startup.is_dir():
        return startup
    return None


def is_registered() -> bool:
    """Check if JARVIS is registered to start with Windows."""
    startup = _get_startup_folder()
    if not startup:
        return False
    # Dev mode creates JARVIS.bat; frozen builds create JARVIS.lnk.
    return (startup / SHORTCUT_NAME).exists() or (startup / "JARVIS.bat").exists()


def register() -> bool:
    """Register JARVIS to start with Windows.

    Creates a .lnk shortcut in the Windows Startup folder.
    """
    startup = _get_startup_folder()
    if not startup:
        logger.error("Cannot find Windows Startup folder")
        return False

    # Determine the executable path
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable)
    else:
        # In development mode, create a batch file launcher
        python_exe = sys.executable
        project_root = Path(__file__).resolve().parent.parent
        batch_content = f'@echo off\n"{python_exe}" -m desktop --start-minimized\n'
        batch_path = startup / "JARVIS.bat"
        try:
            batch_path.write_text(batch_content, encoding="utf-8")
            logger.info(f"Created startup batch: {batch_path}")
            return True
        except OSError as e:
            logger.error(f"Failed to create startup batch: {e}")
            return False

    # Create .lnk shortcut using PowerShell
    try:
        import subprocess
        ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{startup / SHORTCUT_NAME}")
$Shortcut.TargetPath = "{exe_path}"
$Shortcut.Arguments = "--start-minimized"
$Shortcut.WorkingDirectory = "{exe_path.parent}"
$Shortcut.Save()
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            logger.info(f"Registered JARVIS for startup: {startup / SHORTCUT_NAME}")
            return True
        else:
            logger.error(f"Failed to create shortcut: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Failed to register startup: {e}")
        return False


def unregister() -> bool:
    """Unregister JARVIS from Windows startup."""
    startup = _get_startup_folder()
    if not startup:
        return False

    for name in [SHORTCUT_NAME, "JARVIS.bat"]:
        path = startup / name
        if path.exists():
            try:
                path.unlink()
                logger.info(f"Removed startup entry: {path}")
            except OSError as e:
                logger.error(f"Failed to remove startup entry: {e}")
                return False

    return True
