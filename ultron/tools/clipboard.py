"""V1 clipboard tools — cross-platform (Windows PowerShell, Linux xclip/xsel)."""

from __future__ import annotations

import subprocess
from typing import Any, Dict

from ultron.platform import is_windows, is_posix
from ultron.tools.base import Tool


class GetClipboard(Tool):
    name = "get_clipboard"
    description = "Return the current clipboard text, or null if the clipboard holds non-text."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": ["string", "null"]},
        },
    }

    def run(self, **_: Any) -> Dict[str, Any]:
        if is_windows():
            return self._get_windows()
        return self._get_posix()

    def _get_windows(self) -> Dict[str, Any]:
        from ultron.tools._windows import ps_error, ps_ok, ps_stdout, run_powershell, unb64

        script = (
            "$t = Get-Clipboard -Raw; "
            "if ($null -eq $t) { Write-Output 'NULL' } "
            "else { [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($t)) }"
        )
        proc = run_powershell(script, timeout=30, text_output=True)
        if not ps_ok(proc):
            return {"error": f"get_clipboard failed: {ps_error(proc)}"}
        out = ps_stdout(proc)
        if not out or out == "NULL":
            return {"text": None}
        try:
            return {"text": unb64(out)}
        except Exception as exc:
            return {"error": f"clipboard decode failed: {exc}"}

    def _get_posix(self) -> Dict[str, Any]:
        """Get clipboard via xclip or xsel."""
        for cmd in [["xclip", "-selection", "clipboard", "-o"],
                     ["xsel", "--clipboard", "--output"]]:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5,
                )
                if proc.returncode == 0:
                    return {"text": proc.stdout}
            except FileNotFoundError:
                continue
        return {"error": "No clipboard tool found. Install xclip or xsel."}


class SetClipboard(Tool):
    name = "set_clipboard"
    description = "Replace the clipboard contents with the given text."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to place on the clipboard."},
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "set": {"type": "boolean"},
            "characters": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, text: str, **_: Any) -> Dict[str, Any]:
        if is_windows():
            return self._set_windows(text)
        return self._set_posix(text)

    def _set_windows(self, text: str) -> Dict[str, Any]:
        from ultron.tools._windows import b64, ps_error, ps_ok, run_powershell

        script = (
            "$b = [Convert]::FromBase64String('" + b64(text) + "'); "
            "$t = [System.Text.Encoding]::UTF8.GetString($b); "
            "Set-Clipboard -Value $t"
        )
        proc = run_powershell(script, timeout=30)
        if not ps_ok(proc):
            return {"error": f"set_clipboard failed: {ps_error(proc)}"}
        return {"set": True, "characters": len(text)}

    def _set_posix(self, text: str) -> Dict[str, Any]:
        """Set clipboard via xclip or xsel."""
        for cmd in [["xclip", "-selection", "clipboard"],
                     ["xsel", "--clipboard", "--input"]]:
            try:
                proc = subprocess.run(
                    cmd, input=text, capture_output=True, text=True, timeout=5,
                )
                if proc.returncode == 0:
                    return {"set": True, "characters": len(text)}
            except FileNotFoundError:
                continue
        return {"error": "No clipboard tool found. Install xclip or xsel."}
