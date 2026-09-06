"""V1 clipboard tools (Windows built-in Get-Clipboard / Set-Clipboard)."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._windows import b64, ps_error, ps_ok, run_powershell, unb64
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
        script = (
            "$t = Get-Clipboard -Raw; "
            "if ($null -eq $t) { Write-Output 'NULL' } "
            "else { [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($t)) }"
        )
        proc = run_powershell(script, timeout=30, text_output=True)
        if not ps_ok(proc):
            return {"error": f"get_clipboard failed: {ps_error(proc)}"}
        out = proc.stdout.strip()
        if not out or out == "NULL":
            return {"text": None}
        try:
            return {"text": unb64(out)}
        except Exception as exc:
            return {"error": f"clipboard decode failed: {exc}"}


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
        script = (
            "$b = [Convert]::FromBase64String('" + b64(text) + "'); "
            "$t = [System.Text.Encoding]::UTF8.GetString($b); "
            "Set-Clipboard -Value $t"
        )
        proc = run_powershell(script, timeout=30)
        if not ps_ok(proc):
            return {"error": f"set_clipboard failed: {ps_error(proc)}"}
        return {"set": True, "characters": len(text)}
