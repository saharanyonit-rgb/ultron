"""Calendar service for JARVIS — persistent event storage and retrieval."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.services.base import BaseService

logger = logging.getLogger("ultron.services.calendar")


class CalendarService(BaseService):
    """Manages calendar events with JSON file persistence."""

    _data_file = "calendar.json"

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: Optional[str] = None,
        description: str = "",
        timezone: str = "UTC",
        recurrence: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new calendar event."""
        now = self._now_iso()
        event_id = self._generate_id()
        event = {
            "id": event_id,
            "title": str(title).strip(),
            "description": str(description).strip(),
            "start_time": start_time,
            "end_time": end_time,
            "timezone": timezone,
            "recurrence": recurrence,
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }
        self._data["items"].append(event)
        self._persist()
        logger.info("Calendar event created: %s", event_id)
        return event

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single event by ID."""
        for item in self._items():
            if item.get("id") == event_id:
                return item
        return None

    def list_events(
        self,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List events, optionally filtered by time range."""
        events = self._items()

        if from_time:
            try:
                from_dt = datetime.fromisoformat(from_time)
                events = [e for e in events if datetime.fromisoformat(e["start_time"]) >= from_dt]
            except (ValueError, KeyError):
                pass

        if to_time:
            try:
                to_dt = datetime.fromisoformat(to_time)
                events = [e for e in events if datetime.fromisoformat(e["start_time"]) <= to_dt]
            except (ValueError, KeyError):
                pass

        events.sort(key=lambda e: e.get("start_time", ""))
        return events[:limit]

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        timezone: Optional[str] = None,
        recurrence: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an existing event."""
        for item in self._data["items"]:
            if item.get("id") == event_id:
                if title is not None:
                    item["title"] = str(title).strip()
                if description is not None:
                    item["description"] = str(description).strip()
                if start_time is not None:
                    item["start_time"] = start_time
                if end_time is not None:
                    item["end_time"] = end_time
                if timezone is not None:
                    item["timezone"] = timezone
                if recurrence is not None:
                    item["recurrence"] = recurrence
                if metadata is not None:
                    item["metadata"] = metadata
                item["updated_at"] = self._now_iso()
                self._persist()
                logger.info("Calendar event updated: %s", event_id)
                return item
        return None

    def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID."""
        items = self._data["items"]
        for i, item in enumerate(items):
            if item.get("id") == event_id:
                self._data["items"].pop(i)
                self._persist()
                logger.info("Calendar event deleted: %s", event_id)
                return True
        return False

    def search_events(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search events by title or description."""
        q = query.lower()
        events = [
            e for e in self._items()
            if q in e.get("title", "").lower() or q in e.get("description", "").lower()
        ]
        events.sort(key=lambda e: e.get("start_time", ""))
        return events[:limit]

    def get_upcoming(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get the next N upcoming events."""
        now = datetime.now(timezone.utc).isoformat()
        upcoming = [
            e for e in self._items()
            if e.get("start_time", "") >= now
        ]
        upcoming.sort(key=lambda e: e.get("start_time", ""))
        return upcoming[:count]


_calendar_service: Optional[CalendarService] = None


def get_calendar_service(data_dir: Optional[Path] = None) -> CalendarService:
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService(data_dir)
    return _calendar_service
