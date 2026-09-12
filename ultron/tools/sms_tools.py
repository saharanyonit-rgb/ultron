"""SMS tools for Android — send, read, and list text messages."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux
from ultron.tools.base import Tool


class SendSms(Tool):
    """Send an SMS message to a phone number or contact."""

    name = "send_sms"
    description = "Send a text message (SMS) to a phone number or contact name."
    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient phone number or contact name.",
            },
            "message": {
                "type": "string",
                "description": "The text message to send.",
            },
        },
        "required": ["to", "message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "to": {"type": "string"},
            "sent": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, to: str = "", message: str = "", **kwargs: Any) -> Dict[str, Any]:
        target = to or kwargs.get("recipient") or kwargs.get("number") or ""
        text = message or kwargs.get("text") or kwargs.get("body") or ""
        if not target:
            return {"error": "No recipient specified", "success": False, "sent": False}
        if not text:
            return {"error": "No message text provided", "success": False, "sent": False}

        result = run_termux("sms-send", args=["-n", target], stdin_text=text)
        return {"success": result.ok, "to": target, "sent": result.ok, "error": result.stderr or None}


class ReadSms(Tool):
    """Read recent SMS messages."""

    name = "read_sms"
    description = "Read recent SMS/text messages, optionally filtered by sender or limit."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max number of messages to return. Default 10.",
                "default": 10,
            },
            "sender": {
                "type": "string",
                "description": "Filter messages by sender phone number or contact name.",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "messages": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, limit: int = 10, sender: str = "", **kwargs: Any) -> Dict[str, Any]:
        target = sender or kwargs.get("from") or kwargs.get("contact") or ""
        args = ["-l", str(limit)]
        if target:
            args = ["-n", target, "-l", str(limit)]

        result = run_termux("sms-list", args=args, parse_json=True)
        if not result.ok:
            return {"messages": [], "count": 0, "error": result.stderr}

        messages = result.data if isinstance(result.data, list) else []
        return {"messages": messages[:limit], "count": len(messages[:limit])}


class ListSms(Tool):
    """List recent SMS conversations."""

    name = "list_sms"
    description = "List recent SMS messages with sender, body, and timestamp."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max messages to list. Default 20.",
                "default": 20,
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "messages": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, limit: int = 20, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("sms-list", args=["-l", str(limit)], parse_json=True)
        if not result.ok:
            return {"messages": [], "count": 0, "error": result.stderr}

        messages = result.data if isinstance(result.data, list) else []
        return {"messages": messages[:limit], "count": len(messages[:limit])}


__all__ = ["SendSms", "ReadSms", "ListSms"]
