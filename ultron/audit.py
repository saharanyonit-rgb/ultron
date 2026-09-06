"""Audit event system for JARVIS Phase 4.

Records structured execution events for observability:
  - request_received
  - plan_created
  - agent_selected
  - tool_requested
  - permission_decision
  - tool_execution
  - tool_result
  - verification_result
  - retry
  - replan
  - final_response

Each event includes structured metadata for reconstruction.
Sensitive credentials are never stored in logs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.audit")


class EventType(str, Enum):
    REQUEST_RECEIVED = "request_received"
    PLAN_CREATED = "plan_created"
    AGENT_SELECTED = "agent_selected"
    TOOL_REQUESTED = "tool_requested"
    PERMISSION_DECIDED = "permission_decided"
    TOOL_EXECUTED = "tool_executed"
    TOOL_RESULT = "tool_result"
    VERIFICATION_RESULT = "verification_result"
    RETRY = "retry"
    REPLAN = "replan"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    RECOVERY_ACTION = "recovery_action"
    SANDBOX_CREATED = "sandbox_created"
    SANDBOX_EXECUTED = "sandbox_executed"
    FINAL_RESPONSE = "final_response"


# Sensitive keys to redact
SENSITIVE_KEYS = {
    "api_key", "apikey", "api-key", "secret", "password", "token",
    "authorization", "credentials", "access_token", "refresh_token",
}


@dataclass
class AuditEvent:
    """A single audit event."""

    event_type: EventType
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str = ""
    task_id: str = ""
    step_id: str = ""
    tool_name: str = ""
    agent_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "agent_name": self.agent_name,
            "metadata": self._redact_metadata(self.metadata),
            "success": self.success,
            "error": self.error,
        }

    def _redact_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from metadata."""
        redacted = {}
        for key, value in metadata.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_metadata(value)
            else:
                redacted[key] = value
        return redacted


class AuditLogger:
    """Structured audit logging system."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path else None
        self._events: List[AuditEvent] = []
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def events(self) -> List[AuditEvent]:
        return list(self._events)

    def log(self, event: AuditEvent) -> None:
        """Record an audit event."""
        self._events.append(event)

        # Also log to Python logger
        log_msg = f"[{event.event_type.value}] {event.tool_name or event.agent_name or 'system'}"
        if event.error:
            logger.warning("%s - ERROR: %s", log_msg, event.error)
        else:
            logger.info("%s", log_msg)

        # Persist to file if configured
        if self._path:
            self._persist_event(event)

    def log_request_received(self, request_id: str, user_input: str) -> None:
        self.log(AuditEvent(
            event_type=EventType.REQUEST_RECEIVED,
            request_id=request_id,
            metadata={"input_length": len(user_input)},
        ))

    def log_plan_created(self, request_id: str, plan_id: str, step_count: int) -> None:
        self.log(AuditEvent(
            event_type=EventType.PLAN_CREATED,
            request_id=request_id,
            metadata={"plan_id": plan_id, "step_count": step_count},
        ))

    def log_agent_selected(self, request_id: str, agent_name: str) -> None:
        self.log(AuditEvent(
            event_type=EventType.AGENT_SELECTED,
            request_id=request_id,
            agent_name=agent_name,
        ))

    def log_tool_requested(
        self, request_id: str, tool_name: str, arguments: Dict[str, Any]
    ) -> None:
        self.log(AuditEvent(
            event_type=EventType.TOOL_REQUESTED,
            request_id=request_id,
            tool_name=tool_name,
            metadata={"arguments": arguments},
        ))

    def log_permission_decision(
        self, request_id: str, tool_name: str, allowed: bool, risk_level: str
    ) -> None:
        self.log(AuditEvent(
            event_type=EventType.PERMISSION_DECIDED,
            request_id=request_id,
            tool_name=tool_name,
            success=allowed,
            metadata={"risk_level": risk_level, "allowed": allowed},
        ))

    def log_tool_executed(
        self, request_id: str, tool_name: str, success: bool, duration_ms: float
    ) -> None:
        self.log(AuditEvent(
            event_type=EventType.TOOL_EXECUTED,
            request_id=request_id,
            tool_name=tool_name,
            success=success,
            metadata={"duration_ms": duration_ms},
        ))

    def log_verification(
        self, request_id: str, tool_name: str, passed: bool, checks: Dict[str, bool]
    ) -> None:
        self.log(AuditEvent(
            event_type=EventType.VERIFICATION_RESULT,
            request_id=request_id,
            tool_name=tool_name,
            success=passed,
            metadata={"checks": checks},
        ))

    def log_retry(self, request_id: str, step_id: str, retry_count: int, reason: str) -> None:
        self.log(AuditEvent(
            event_type=EventType.RETRY,
            request_id=request_id,
            step_id=step_id,
            metadata={"retry_count": retry_count, "reason": reason},
        ))

    def log_recovery(self, request_id: str, action: str, reason: str) -> None:
        self.log(AuditEvent(
            event_type=EventType.RECOVERY_ACTION,
            request_id=request_id,
            metadata={"action": action, "reason": reason},
        ))

    def log_final_response(self, request_id: str, success: bool, response_length: int) -> None:
        self.log(AuditEvent(
            event_type=EventType.FINAL_RESPONSE,
            request_id=request_id,
            success=success,
            metadata={"response_length": response_length},
        ))

    def get_trace(self, request_id: str) -> List[AuditEvent]:
        """Get all events for a specific request."""
        return [e for e in self._events if e.request_id == request_id]

    def get_task_trace(self, task_id: str) -> List[AuditEvent]:
        """Get all events for a specific task."""
        return [e for e in self._events if e.task_id == task_id]

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def _persist_event(self, event: AuditEvent) -> None:
        """Append an event to the audit file."""
        try:
            line = json.dumps(event.to_dict(), ensure_ascii=False, default=str)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            logger.error("Failed to persist audit event: %s", exc)


__all__ = ["EventType", "AuditEvent", "AuditLogger", "SENSITIVE_KEYS"]
