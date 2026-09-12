"""Phone call control tools for Android — via termux-api + am/pm."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux, run_am, run_cmd
from ultron.tools.base import Tool


class MakeCall(Tool):
    """Initiate a phone call."""

    name = "make_call"
    description = "Initiate a phone call to a number or contact name."
    parameters = {
        "type": "object",
        "properties": {
            "number": {
                "type": "string",
                "description": "Phone number or contact name to call.",
            },
        },
        "required": ["number"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "number": {"type": "string"},
        },
    }
    mutates = True

    def run(self, number: str = "", **kwargs: Any) -> Dict[str, Any]:
        target = number or kwargs.get("phone") or kwargs.get("contact") or ""
        if not target:
            return {"error": "No number or contact provided", "success": False}

        import urllib.parse
        encoded = urllib.parse.quote(target)
        result = run_am([
            "start",
            "-a", "android.intent.action.CALL",
            "-d", f"tel:{encoded}",
        ])
        return {"success": result.ok, "number": target, "error": result.stderr or None}


class AnswerCall(Tool):
    """Answer an incoming phone call."""

    name = "answer_call"
    description = "Answer the current incoming phone call."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "5"])
        return {"success": result.ok}


class HangUp(Tool):
    """End a phone call."""

    name = "hang_up"
    description = "End/hang up the current phone call."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "6"])
        return {"success": result.ok}


class GetCallLog(Tool):
    """Retrieve recent call history."""

    name = "get_call_log"
    description = "Get recent call history (incoming, outgoing, missed)."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of recent calls to return. Default 10.",
                "default": 10,
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "calls": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, limit: int = 10, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("call-log", args=[], parse_json=True)
        if not result.ok:
            return {"calls": [], "count": 0, "error": result.stderr}

        calls = result.data if isinstance(result.data, list) else []
        # Each entry: {"number": "...", "type": "incoming", "date": "...", "duration": "..."}
        limited = calls[:limit]
        return {"calls": limited, "count": len(limited)}


class RejectCall(Tool):
    """Reject/decline an incoming call."""

    name = "reject_call"
    description = "Reject or decline an incoming phone call."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "6"])
        return {"success": result.ok}


__all__ = [
    "MakeCall",
    "AnswerCall",
    "HangUp",
    "RejectCall",
    "GetCallLog",
]
