"""Calendar tool — create, list, and manage calendar events."""

from __future__ import annotations

from typing import Any, Dict

from ultron.services import get_calendar_service
from ultron.tools.base import Tool


class CalendarTool(Tool):
    """Tool for creating and managing calendar events."""

    name = "create_calendar_event"
    description = (
        "Create a new calendar event. Use this when the user asks to schedule a meeting, "
        "set up an appointment, add a calendar entry, or block time. "
        "Required: title and start_time. Optional: end_time, description, timezone."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title or name of the event.",
            },
            "start_time": {
                "type": "string",
                "description": "Start time in ISO 8601 format (e.g., '2026-09-03T10:00:00').",
            },
            "end_time": {
                "type": "string",
                "description": "Optional end time in ISO 8601 format.",
            },
            "description": {
                "type": "string",
                "description": "Optional description or notes for the event.",
            },
            "timezone": {
                "type": "string",
                "description": "Timezone for the event (default: UTC).",
            },
        },
        "required": ["title", "start_time"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "start_time": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        title: str,
        start_time: str,
        end_time: str | None = None,
        description: str = "",
        timezone: str = "UTC",
        **_: Any,
    ) -> Dict[str, Any]:
        try:
            service = get_calendar_service()
            event = service.create_event(
                title=title,
                start_time=start_time,
                end_time=end_time,
                description=description,
                timezone=timezone,
            )
            return {"created": True, "event": event}
        except Exception as exc:
            return {"error": f"Failed to create calendar event: {exc}"}


class ListCalendarEventsTool(Tool):
    """List upcoming calendar events."""

    name = "list_calendar_events"
    description = (
        "List upcoming calendar events. Use when the user asks to see their calendar, "
        "list meetings, or check their schedule."
    )
    parameters = {
        "type": "object",
        "properties": {
            "from_time": {
                "type": "string",
                "description": "Optional ISO 8601 datetime to filter events from.",
            },
            "to_time": {
                "type": "string",
                "description": "Optional ISO 8601 datetime to filter events up to.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of events to return (default: 10).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "events": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(
        self,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int = 10,
        **_: Any,
    ) -> Dict[str, Any]:
        try:
            service = get_calendar_service()
            events = service.list_events(from_time=from_time, to_time=to_time, limit=limit)
            return {"events": events, "count": len(events)}
        except Exception as exc:
            return {"error": f"Failed to list events: {exc}", "events": [], "count": 0}
