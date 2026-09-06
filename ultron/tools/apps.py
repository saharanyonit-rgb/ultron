"""V1 app tools: open and close known apps."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._windows import ps_error, ps_ok, ps_quote, ps_stdout, run_powershell
from ultron.tools.base import Tool

KNOWN_APPS: Dict[str, str] = {
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
    "opencode": r"C:\Users\Lenovo\AppData\Roaming\npm\opencode.ps1",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "vs code": r"C:\Users\Lenovo\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
    "visual studio code": r"C:\Users\Lenovo\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
    "code": r"C:\Users\Lenovo\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd",
    "whatsapp": "WhatsApp",
    "whatsapp desktop": "WhatsApp",
    "whatsapp beta": "WhatsAppBeta",
}

_HELP_TEXT = "Known apps: " + ", ".join(sorted(KNOWN_APPS))


def _resolve_app(name: str) -> tuple[str | None, str | None]:
    """Return (target, error). Known names map to shortcuts; a bare .exe path is accepted."""
    key = name.strip().lower()
    if key in KNOWN_APPS:
        return KNOWN_APPS[key], None
    if key.endswith(".exe") or (key.endswith(".exe") is False and "\\" in key):
        return name.strip(), None
    return None, f"unknown app {name!r}. {_HELP_TEXT}"


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
                "description": "A known app name or a path to an .exe.",
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
        },
    }
    mutates = True

    def run(self, app_name: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_name = app_name or kwargs.get("name") or kwargs.get("app") or kwargs.get("target") or ""
        if not target_name:
            return {"error": "Missing 'app_name' parameter"}
        target, error = _resolve_app(target_name)
        if error:
            return {"error": error}
        script = (
            f"$p = Start-Process -FilePath {ps_quote(target)} -PassThru; "
            f"Write-Output $p.Id"
        )
        proc = run_powershell(script, timeout=30)
        if not ps_ok(proc):
            return {"error": f"failed to start {target!r}: {ps_error(proc)}"}
        try:
            pid = int(ps_stdout(proc))
        except ValueError:
            pid = None
        return {"app": target_name, "target": target, "pid": pid}


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
