"""V1 app tools: open and close known apps — cross-platform."""

from __future__ import annotations

import subprocess
from typing import Any, Dict

from ultron.platform import is_windows, is_android, is_posix
from ultron.tools.base import Tool

# Windows known apps
KNOWN_APPS_WINDOWS: Dict[str, str] = {
    "notepad": "notepad",
    "calc": "calc",
    "calculator": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "wordpad": "write",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "control panel": "control",
    "settings": "ms-settings:",
    "microsoft edge": "msedge",
    "edge": "msedge",
    "chrome": "chrome",
    "google chrome": "chrome",
    "whatsapp": "WhatsApp",
}

# Android/Termux known apps (via am start)
KNOWN_APPS_ANDROID: Dict[str, str] = {
    "chrome": "com.android.chrome",
    "google chrome": "com.android.chrome",
    "firefox": "org.mozilla.firefox",
    "settings": "com.android.settings",
    "calculator": "com.android.calculator2",
    "files": "com.android.documentsui",
    "gallery": "com.android.gallery3d",
    "camera": "android.media.action.STILL_IMAGE_CAMERA",
    "whatsapp": "com.whatsapp",
    "terminal": "com.termux",
}

# Linux known apps (via xdg-open or direct)
KNOWN_APPS_LINUX: Dict[str, str] = {
    "chrome": "google-chrome",
    "google chrome": "google-chrome",
    "firefox": "firefox",
    "files": "xdg-open",
    "settings": "xdg-open",
}

HELP_TEXT = "Known apps: " + ", ".join(sorted(
    set(list(KNOWN_APPS_WINDOWS.keys()) + list(KNOWN_APPS_ANDROID.keys()) + list(KNOWN_APPS_LINUX.keys()))
))


def _get_known_apps() -> Dict[str, str]:
    if is_android():
        return KNOWN_APPS_ANDROID
    if is_windows():
        return KNOWN_APPS_WINDOWS
    return KNOWN_APPS_LINUX


def _resolve_app(name: str) -> tuple[str | None, str | None]:
    key = name.strip().lower()
    known = _get_known_apps()
    if key in known:
        return known[key], None
    if is_windows() and (key.endswith(".exe") or "\\" in key):
        return name.strip(), None
    # On Linux/Android, accept any command
    if is_posix():
        return name.strip(), None
    return None, f"unknown app {name!r}. {HELP_TEXT}"


class OpenApp(Tool):
    name = "open_app"
    description = (
        "Launch a known application (e.g. notepad, calc, explorer, settings) "
        "or an executable path. Returns the launched process id."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "A known app name or a path to an .exe / package.",
            },
        },
        "required": ["app_name"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "app": {"type": "string"},
            "target": {"type": "string"},
            "pid": {"type": "integer"},
            "launched": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, app_name: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_name = app_name or kwargs.get("name") or kwargs.get("app") or kwargs.get("target") or ""
        if not target_name:
            return {"error": "Missing 'app_name' parameter", "launched": False}
        target, error = _resolve_app(target_name)
        if error:
            return {"error": error, "launched": False}

        if is_android():
            return self._open_android(target_name, target)
        if is_windows():
            return self._open_windows(target_name, target)
        return self._open_linux(target_name, target)

    def _open_windows(self, target_name: str, target: str) -> Dict[str, Any]:
        from ultron.tools._windows import ps_error, ps_ok, ps_quote, ps_stdout, run_powershell

        script = (
            f"$p = Start-Process -FilePath {ps_quote(target)} -PassThru; "
            f"Write-Output $p.Id"
        )
        proc = run_powershell(script, timeout=30)
        if not ps_ok(proc):
            return {"error": f"failed to start {target!r}: {ps_error(proc)}", "launched": False}
        try:
            pid = int(ps_stdout(proc))
        except ValueError:
            pid = None
        launched = pid is not None
        return {"app": target_name, "target": target, "pid": pid, "launched": launched}

    def _open_android(self, target_name: str, target: str) -> Dict[str, Any]:
        """Open app on Android via Termux am command."""
        try:
            # For intent-based launches (contains a dot and no spaces = package name)
            if "." in target and " " not in target:
                proc = subprocess.run(
                    ["am", "start", "-n", f"{target}/.MainActivity"],
                    capture_output=True, text=True, timeout=10,
                )
                if proc.returncode != 0:
                    # Try without .MainActivity
                    proc = subprocess.run(
                        ["am", "start", "-a", "android.intent.action.MAIN",
                         "-c", "android.intent.category.LAUNCHER", target],
                        capture_output=True, text=True, timeout=10,
                    )
            else:
                # Try xdg-open for URLs or file paths
                proc = subprocess.run(
                    ["xdg-open", target],
                    capture_output=True, text=True, timeout=10,
                )
            return {"app": target_name, "target": target, "launched": proc.returncode == 0}
        except Exception as e:
            return {"error": f"failed to start {target!r}: {e}", "launched": False}

    def _open_linux(self, target_name: str, target: str) -> Dict[str, Any]:
        """Open app on Linux via subprocess."""
        try:
            proc = subprocess.Popen(
                [target],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"app": target_name, "target": target, "pid": proc.pid, "launched": True}
        except FileNotFoundError:
            # Try xdg-open as fallback
            try:
                proc = subprocess.Popen(
                    ["xdg-open", target],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return {"app": target_name, "target": target, "pid": proc.pid, "launched": True}
            except Exception as e:
                return {"error": f"failed to start {target!r}: {e}", "launched": False}


class CloseApp(Tool):
    name = "close_app"
    description = (
        "Close a running application by process name (with or without .exe). "
        "Only affects the named process; nothing else is touched."
    )
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Process name, e.g. 'notepad'."},
        },
        "required": ["app_name"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "closed": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, app_name: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_name = app_name or kwargs.get("name") or kwargs.get("app") or kwargs.get("process") or ""
        proc_name = target_name.strip().removesuffix(".exe")
        if not proc_name:
            return {"error": "app_name is empty"}

        if is_windows():
            return self._close_windows(proc_name)
        return self._close_posix(proc_name)

    def _close_windows(self, proc_name: str) -> Dict[str, Any]:
        from ultron.tools._windows import ps_error, ps_ok, ps_quote, ps_stdout, run_powershell

        script = (
            "try { `$ps = Get-Process -Name "
            + ps_quote(proc_name)
            + " -ErrorAction Stop; if (`$ps) { `$ps | Stop-Process; `$ps | ForEach-Object { Write-Output `$_.ProcessName } } } catch { }; exit 0"
        )
        proc = run_powershell(script, timeout=30)
        if not ps_ok(proc):
            return {"error": f"failed to close {proc_name!r}: {ps_error(proc)}"}
        closed = [line for line in ps_stdout(proc).splitlines() if line]
        if not closed:
            return {"closed": [], "count": 0, "note": f"{proc_name} was not running"}
        return {"closed": closed, "count": len(closed)}

    def _close_posix(self, proc_name: str) -> Dict[str, Any]:
        """Close app on Linux/Android via pkill."""
        try:
            proc = subprocess.run(
                ["pkill", "-f", proc_name],
                capture_output=True, text=True, timeout=10,
            )
            # pkill returns 0 if at least one process was killed
            if proc.returncode == 0:
                return {"closed": [proc_name], "count": 1}
            return {"closed": [], "count": 0, "note": f"{proc_name} was not running"}
        except Exception as e:
            return {"error": f"failed to close {proc_name!r}: {e}"}
