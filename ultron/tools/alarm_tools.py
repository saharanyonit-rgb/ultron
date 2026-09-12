"""Alarm management tools for Android — set, list, cancel alarms."""

from __future__ import annotations

import json
from typing import Any, Dict

from ultron.tools._termux import run_termux, run_cmd, run_am
from ultron.tools.base import Tool


class SetAlarm(Tool):
    """Set an alarm for a specific time."""

    name = "set_alarm"
    description = "Set an alarm for a given time. Format: HH:MM (24h) or use 'in X minutes'."
    parameters = {
        "type": "object",
        "properties": {
            "time": {
                "type": "string",
                "description": "Alarm time: 'HH:MM' (24h) or 'in X minutes'.",
            },
            "label": {
                "type": "string",
                "description": "Label/description for the alarm (optional).",
            },
        },
        "required": ["time"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "time": {"type": "string"},
            "label": {"type": "string"},
        },
    }
    mutates = True

    def run(self, time: str = "", label: str = "", **kwargs: Any) -> Dict[str, Any]:
        t = time or kwargs.get("alarm_time") or kwargs.get("hour") or ""
        l = label or kwargs.get("description") or kwargs.get("name") or "Ultron Alarm"
        if not t:
            return {"error": "No time specified", "success": False}

        result = run_termux("alarm-set", args=["-t", t, "-e", l])
        return {"success": result.ok, "time": t, "label": l, "error": result.stderr or None}


class ListAlarms(Tool):
    """List all currently set alarms."""

    name = "list_alarms"
    description = "List all active alarms on the device."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "alarms": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("alarm-list", parse_json=True)
        if not result.ok:
            return {"alarms": [], "count": 0, "error": result.stderr}

        alarms = result.data if isinstance(result.data, list) else []
        return {"alarms": alarms, "count": len(alarms)}


class CancelAlarm(Tool):
    """Cancel an alarm by ID or time."""

    name = "cancel_alarm"
    description = "Cancel an active alarm by its ID."
    parameters = {
        "type": "object",
        "properties": {
            "alarm_id": {
                "type": "string",
                "description": "The alarm ID to cancel (from list_alarms).",
            },
        },
        "required": ["alarm_id"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "cancelled_id": {"type": "string"},
        },
    }
    mutates = True

    def run(self, alarm_id: str = "", **kwargs: Any) -> Dict[str, Any]:
        aid = alarm_id or kwargs.get("id") or kwargs.get("alarm") or ""
        if not aid:
            return {"error": "No alarm ID provided", "success": False}
        result = run_termux("alarm-cancel", args=[str(aid)])
        return {"success": result.ok, "cancelled_id": str(aid), "error": result.stderr or None}


class SetTimer(Tool):
    """Set a countdown timer."""

    name = "set_timer"
    description = "Set a countdown timer for a specified duration in seconds."
    parameters = {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer",
                "description": "Timer duration in seconds.",
            },
        },
        "required": ["seconds"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "seconds": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, seconds: int = 60, **kwargs: Any) -> Dict[str, Any]:
        s = kwargs.get("duration") or kwargs.get("time") or seconds
        s = int(s)
        if s <= 0:
            return {"error": "Duration must be positive", "success": False}

        result = run_termux("alarm-set", args=["-t", f"in {s} seconds", "-e", "Ultron Timer"])
        return {"success": result.ok, "seconds": s, "error": result.stderr or None}


__all__ = ["SetAlarm", "ListAlarms", "CancelAlarm", "SetTimer"]
