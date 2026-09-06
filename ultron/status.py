"""Streaming execution status for JARVIS Phase 4.

Reports execution progress through an event abstraction:
  - Task started
  - Planning...
  - Agent selected
  - Step executing...
  - Step verified
  - Completed

Future CLI/UI interfaces can subscribe to events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ultron.status")


class StatusEvent(str, Enum):
    TASK_STARTED = "task_started"
    PLANNING = "planning"
    PLAN_CREATED = "plan_created"
    AGENT_SELECTED = "agent_selected"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    RETRYING = "retrying"
    RECOVERING = "recovering"
    REPLANING = "replaning"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class StatusUpdate:
    """A single status update."""

    event: StatusEvent
    message: str = ""
    task_id: str = ""
    step_id: str = ""
    progress: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event.value,
            "message": self.message,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "progress": self.progress,
            "metadata": self.metadata,
        }


class StatusSubscriber(ABC):
    """Abstract subscriber for status updates."""

    @abstractmethod
    def on_status(self, update: StatusUpdate) -> None:
        """Handle a status update."""
        ...


class CallbackSubscriber(StatusSubscriber):
    """Status subscriber that calls a callback function."""

    def __init__(self, callback: Callable[[StatusUpdate], None]) -> None:
        self._callback = callback

    def on_status(self, update: StatusUpdate) -> None:
        self._callback(update)


class StatusReporter:
    """Reports execution status to subscribers."""

    def __init__(self) -> None:
        self._subscribers: List[StatusSubscriber] = []
        self._history: List[StatusUpdate] = []

    @property
    def history(self) -> List[StatusUpdate]:
        return list(self._history)

    def subscribe(self, subscriber: StatusSubscriber) -> None:
        """Add a status subscriber."""
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: StatusSubscriber) -> None:
        """Remove a status subscriber."""
        self._subscribers.remove(subscriber)

    def report(
        self,
        event: StatusEvent,
        message: str = "",
        task_id: str = "",
        step_id: str = "",
        progress: float = 0.0,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Report a status update to all subscribers."""
        update = StatusUpdate(
            event=event,
            message=message,
            task_id=task_id,
            step_id=step_id,
            progress=progress,
            metadata=metadata or {},
        )
        self._history.append(update)
        for subscriber in self._subscribers:
            try:
                subscriber.on_status(update)
            except Exception as exc:
                logger.error("Status subscriber error: %s", exc)

    def task_started(self, task_id: str, description: str = "") -> None:
        self.report(StatusEvent.TASK_STARTED, description, task_id=task_id)

    def planning(self, task_id: str) -> None:
        self.report(StatusEvent.PLANNING, "Creating plan...", task_id=task_id)

    def plan_created(self, task_id: str, step_count: int) -> None:
        self.report(
            StatusEvent.PLAN_CREATED,
            f"Plan created with {step_count} steps",
            task_id=task_id,
            metadata={"step_count": step_count},
        )

    def agent_selected(self, task_id: str, agent_name: str) -> None:
        self.report(
            StatusEvent.AGENT_SELECTED,
            f"Selected agent: {agent_name}",
            task_id=task_id,
            metadata={"agent_name": agent_name},
        )

    def step_started(self, task_id: str, step_id: str, objective: str, progress: float) -> None:
        self.report(
            StatusEvent.STEP_STARTED,
            f"Executing: {objective}",
            task_id=task_id,
            step_id=step_id,
            progress=progress,
        )

    def step_completed(self, task_id: str, step_id: str, progress: float) -> None:
        self.report(
            StatusEvent.STEP_COMPLETED,
            f"Step {step_id} completed",
            task_id=task_id,
            step_id=step_id,
            progress=progress,
        )

    def step_failed(self, task_id: str, step_id: str, error: str) -> None:
        self.report(
            StatusEvent.STEP_FAILED,
            f"Step {step_id} failed: {error}",
            task_id=task_id,
            step_id=step_id,
            metadata={"error": error},
        )

    def verifying(self, task_id: str, step_id: str) -> None:
        self.report(
            StatusEvent.VERIFYING,
            f"Verifying step {step_id}",
            task_id=task_id,
            step_id=step_id,
        )

    def verified(self, task_id: str, step_id: str, passed: bool) -> None:
        self.report(
            StatusEvent.VERIFIED,
            f"Verification {'passed' if passed else 'failed'}",
            task_id=task_id,
            step_id=step_id,
            metadata={"passed": passed},
        )

    def completed(self, task_id: str) -> None:
        self.report(StatusEvent.COMPLETED, "Task completed", task_id=task_id, progress=1.0)

    def failed(self, task_id: str, reason: str) -> None:
        self.report(StatusEvent.FAILED, f"Task failed: {reason}", task_id=task_id)

    def retrying(self, task_id: str, step_id: str = "") -> None:
        self.report(
            StatusEvent.RETRYING,
            f"Retrying step {step_id}",
            task_id=task_id,
            step_id=step_id,
        )

    def recovering(self, task_id: str, message: str = "Recovering...") -> None:
        self.report(
            StatusEvent.RECOVERING,
            message,
            task_id=task_id,
        )

    def replaning(self, task_id: str, message: str = "Replanning...") -> None:
        self.report(
            StatusEvent.REPLANING,
            message,
            task_id=task_id,
        )

    def clear_history(self) -> None:
        self._history.clear()


__all__ = [
    "StatusEvent",
    "StatusUpdate",
    "StatusSubscriber",
    "CallbackSubscriber",
    "StatusReporter",
]
