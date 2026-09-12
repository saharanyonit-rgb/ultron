"""Reminder tool — create and manage reminders with scheduled notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from ultron.services import get_reminders_service, ReminderStatus
from ultron.tools.base import Tool


class CreateReminderTool(Tool):
    """Create a new reminder that fires at a specified time."""

    name = "create_reminder"
    description = (
        "Create a reminder that will notify the user at a specified time. "
        "Use when the user asks to be reminded, set a reminder, or get a notification. "
        "Supports relative times like 'in 10 minutes', 'tomorrow at 3pm', or absolute times."
    )
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The reminder message or note to the user.",
            },
            "trigger_time": {
                "type": "string",
                "description": (
                    "When to fire the reminder. ISO 8601 format or relative: "
                    "'2026-09-03T15:00:00', 'in 10 minutes', 'tomorrow at 3pm'. "
                    "If using relative language, also set relative_delta."
                ),
            },
            "relative_delta": {
                "type": "string",
                "description": (
                    "For relative times: 'minutes', 'hours', 'days'. "
                    "E.g., delta='minutes', delta_value=10 means 'in 10 minutes'."
                ),
            },
            "delta_value": {
                "type": "integer",
                "description": "Numeric value for relative delta (e.g., 10 for 'in 10 minutes').",
            },
            "recurrence": {
                "type": "string",
                "description": "Optional recurrence: 'daily', 'weekly', 'hourly'.",
            },
        },
        "required": ["message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "message": {"type": "string"},
            "trigger_time": {"type": "string"},
            "status": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        message: str,
        trigger_time: str | None = None,
        relative_delta: str | None = None,
        delta_value: int | None = None,
        recurrence: str | None = None,
        **_: Any,
    ) -> Dict[str, Any]:
        if not trigger_time:
            if relative_delta and delta_value:
                now = datetime.now(timezone.utc)
                if relative_delta == "minutes":
                    trigger = now + timedelta(minutes=delta_value)
                elif relative_delta == "hours":
                    trigger = now + timedelta(hours=delta_value)
                elif relative_delta == "days":
                    trigger = now + timedelta(days=delta_value)
                else:
                    return {"error": f"Unknown relative_delta: {relative_delta}"}
                trigger_time = trigger.isoformat()
            else:
                return {"error": "Either trigger_time or relative_delta+delta_value must be provided."}

        try:
            service = get_reminders_service()
            reminder = service.create_reminder(
                message=message,
                trigger_time=trigger_time,
                recurrence=recurrence,
            )
            return {"created": True, "reminder": reminder}
        except Exception as exc:
            return {"error": f"Failed to create reminder: {exc}"}


class ListRemindersTool(Tool):
    """List reminders, optionally filtered by status."""

    name = "list_reminders"
    description = (
        "List reminders. Use when the user asks to see reminders, list reminders, "
        "or check upcoming notifications."
    )
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Filter by status: 'pending', 'triggered', 'cancelled'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of reminders to return (default: 20).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "reminders": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, status: str | None = None, limit: int = 20, **_: Any) -> Dict[str, Any]:
        try:
            service = get_reminders_service()
            reminders = service.list_reminders(status=status, limit=limit)
            return {"reminders": reminders, "count": len(reminders)}
        except Exception as exc:
            return {"error": f"Failed to list reminders: {exc}", "reminders": [], "count": 0}


class CancelReminderTool(Tool):
    """Cancel a pending reminder."""

    name = "cancel_reminder"
    description = "Cancel a pending reminder by its ID. Use when the user asks to cancel or dismiss a reminder."
    parameters = {
        "type": "object",
        "properties": {
            "reminder_id": {
                "type": "string",
                "description": "The ID of the reminder to cancel.",
            },
        },
        "required": ["reminder_id"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "cancelled": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, reminder_id: str, **_: Any) -> Dict[str, Any]:
        try:
            service = get_reminders_service()
            if service.cancel_reminder(reminder_id):
                return {"cancelled": True}
            return {"cancelled": False, "error": f"Reminder {reminder_id} not found or already cancelled"}
        except Exception as exc:
            return {"error": f"Failed to cancel reminder: {exc}"}
