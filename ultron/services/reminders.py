"""Reminders service for JARVIS — persistent reminder storage with background scheduling."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ultron.services.base import BaseService

logger = logging.getLogger("ultron.services.reminders")


class ReminderStatus(str, Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass
class Reminder:
    id: str
    message: str
    trigger_time: str
    recurrence: Optional[str] = None
    status: ReminderStatus = ReminderStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    triggered_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "trigger_time": self.trigger_time,
            "recurrence": self.recurrence,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "triggered_at": self.triggered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        return cls(
            id=data["id"],
            message=data["message"],
            trigger_time=data["trigger_time"],
            recurrence=data.get("recurrence"),
            status=ReminderStatus(data.get("status", "pending")),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            triggered_at=data.get("triggered_at"),
        )


class RemindersService(BaseService):
    """Manages reminders with JSON persistence and background scheduling."""

    _data_file = "reminders.json"

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        super().__init__(data_dir)
        self._timers: Dict[str, threading.Timer] = {}
        self._notification_callback: Optional[Callable[[Reminder], None]] = None
        self._schedule_pending()

    def set_notification_callback(self, callback: Callable[[Reminder], None]) -> None:
        """Set a callback to be called when a reminder fires."""
        self._notification_callback = callback

    def create_reminder(
        self,
        message: str,
        trigger_time: str,
        recurrence: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new reminder and schedule it."""
        now = self._now_iso()
        reminder_id = self._generate_id()
        reminder = Reminder(
            id=reminder_id,
            message=str(message).strip(),
            trigger_time=trigger_time,
            recurrence=recurrence,
            status=ReminderStatus.PENDING,
            metadata=metadata or {},
            created_at=now,
        )

        self._data["items"].append(reminder.to_dict())
        self._persist()
        self._schedule_reminder(reminder)
        logger.info("Reminder created and scheduled: %s", reminder_id)
        return reminder.to_dict()

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single reminder by ID."""
        for item in self._items():
            if item.get("id") == reminder_id:
                return item
        return None

    def list_reminders(
        self,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List reminders, optionally filtered by status."""
        reminders = self._items()
        if status:
            reminders = [r for r in reminders if r.get("status") == status]
        reminders.sort(key=lambda r: r.get("trigger_time", ""))
        return reminders[:limit]

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a pending reminder."""
        timer = self._timers.pop(reminder_id, None)
        if timer:
            timer.cancel()

        for item in self._data["items"]:
            if item.get("id") == reminder_id and item.get("status") == ReminderStatus.PENDING.value:
                item["status"] = ReminderStatus.CANCELLED.value
                self._persist()
                logger.info("Reminder cancelled: %s", reminder_id)
                return True
        return False

    def delete_reminder(self, reminder_id: str) -> bool:
        """Permanently delete a reminder."""
        self.cancel_reminder(reminder_id)
        items = self._data["items"]
        for i, item in enumerate(items):
            if item.get("id") == reminder_id:
                self._data["items"].pop(i)
                self._persist()
                logger.info("Reminder deleted: %s", reminder_id)
                return True
        return False

    def _schedule_reminder(self, reminder: Reminder) -> None:
        """Schedule a reminder to fire at its trigger_time."""
        try:
            trigger_dt = datetime.fromisoformat(reminder.trigger_time)
            if trigger_dt.tzinfo is None:
                trigger_dt = trigger_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delay = (trigger_dt - now).total_seconds()
            if delay <= 0:
                logger.info("Reminder %s is already past, triggering immediately", reminder.id)
                self._fire_reminder(reminder)
                return
            MAX_TIMER_DELAY = 86400.0  # 1 day max per timer wait to prevent Windows OverflowError
            actual_delay = min(delay, MAX_TIMER_DELAY)
            if delay > MAX_TIMER_DELAY:
                timer = threading.Timer(actual_delay, self._schedule_reminder, args=(reminder,))
            else:
                timer = threading.Timer(actual_delay, self._fire_reminder, args=(reminder,))
            timer.daemon = True
            self._timers[reminder.id] = timer
            timer.start()
            logger.debug("Reminder %s scheduled in %.0f seconds", reminder.id, actual_delay)
        except Exception as exc:
            logger.error("Failed to schedule reminder %s: %s", reminder.id, exc)

    def _fire_reminder(self, reminder: Reminder) -> None:
        """Fire a reminder: update status and invoke callback."""
        reminder_id = reminder.id
        for item in self._data["items"]:
            if item.get("id") == reminder_id:
                item["status"] = ReminderStatus.TRIGGERED.value
                item["triggered_at"] = self._now_iso()
                self._persist()
                break

        if self._notification_callback:
            try:
                self._notification_callback(reminder)
            except Exception as exc:
                logger.error("Notification callback error for reminder %s: %s", reminder_id, exc)

        logger.info("Reminder fired: %s — %s", reminder_id, reminder.message)

        if reminder.recurrence:
            next_time = self._calculate_next_recurrence(reminder.trigger_time, reminder.recurrence)
            if next_time:
                self.create_reminder(
                    message=reminder.message,
                    trigger_time=next_time,
                    recurrence=reminder.recurrence,
                    metadata=reminder.metadata,
                )

    def _schedule_pending(self) -> None:
        """Re-schedule all pending reminders after restart."""
        for item in self._items():
            if item.get("status") == ReminderStatus.PENDING.value:
                try:
                    reminder = Reminder.from_dict(item)
                    self._schedule_reminder(reminder)
                except Exception as exc:
                    logger.error("Failed to re-schedule reminder %s: %s", item.get("id"), exc)

    def _calculate_next_recurrence(self, trigger_time: str, recurrence: str) -> Optional[str]:
        """Calculate the next occurrence for a recurrence rule."""
        try:
            dt = datetime.fromisoformat(trigger_time)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            if recurrence == "daily":
                next_dt = dt.replace(day=dt.day + 1)
            elif recurrence == "weekly":
                next_dt = dt.replace(day=dt.day + 7)
            elif recurrence == "hourly":
                from datetime import timedelta
                next_dt = dt + timedelta(hours=1)
            else:
                return None

            return next_dt.isoformat()
        except Exception:
            return None

    def get_upcoming(self, count: int = 5) -> List[Dict[str, Any]]:
        """Get the next N pending reminders."""
        pending = [
            r for r in self._items()
            if r.get("status") == ReminderStatus.PENDING.value
        ]
        pending.sort(key=lambda r: r.get("trigger_time", ""))
        return pending[:count]


_reminders_service: Optional[RemindersService] = None


def get_reminders_service(data_dir: Optional[Path] = None) -> RemindersService:
    global _reminders_service
    if _reminders_service is None:
        _reminders_service = RemindersService(data_dir)
    return _reminders_service
