"""Permission Manager for JARVIS Web UI.

Manages asynchronous permission requests via SSE.
Coordinates between the orchestrator's synchronous permission calls
and the web UI's asynchronous user interaction.
"""

from __future__ import annotations

import threading
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ultron.risk import RiskLevel

logger = logging.getLogger("ultron.permission_manager")


SENSITIVE_KEYS = {
    "api_key", "apikey", "api-key", "secret", "password", "token",
    "authorization", "credentials", "access_token", "refresh_token",
    "auth", "session", "credential",
}


def redact_sensitive(args: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive information from arguments."""
    if not args:
        return {}
    redacted = {}
    for k, v in args.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            redacted[k] = "***REDACTED***"
        elif isinstance(v, dict):
            redacted[k] = redact_sensitive(v)
        else:
            redacted[k] = v
    return redacted


@dataclass
class PendingPermission:
    """Represents a pending permission request."""
    permission_id: str
    tool_name: str
    risk_level: RiskLevel
    reason: str
    arguments: Dict[str, Any]
    decision: Optional[bool] = None
    event: threading.Event = field(default_factory=threading.Event)
    created_at: float = field(default_factory=lambda: __import__("time").time())


class PermissionManager:
    """Manages permission requests for the web UI.

    Integrates with SSE to emit permission.required events
    and waits for user decisions via API calls.
    """

    def __init__(self, broadcaster: Optional[Any] = None) -> None:
        self._pending: Dict[str, PendingPermission] = {}
        self._lock = threading.Lock()
        self._broadcaster = broadcaster
        self._timeout_seconds = 300  # 5 minutes

    def set_broadcaster(self, broadcaster: Any) -> None:
        """Set the SSE broadcaster for emitting events."""
        self._broadcaster = broadcaster

    def request_permission(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        arguments: Dict[str, Any],
    ) -> bool:
        """Request permission from user. Blocks until decision is received.

        This is called synchronously by the orchestrator when it needs
        permission to execute a tool.

        Args:
            tool_name: Name of the tool requesting permission
            risk_level: Risk classification
            arguments: Tool arguments (secrets will be redacted)

        Returns:
            True if user allowed, False if denied or timeout
        """
        permission_id = str(uuid.uuid4())[:12]
        redacted_args = redact_sensitive(arguments)

        pending = PendingPermission(
            permission_id=permission_id,
            tool_name=tool_name,
            risk_level=risk_level,
            reason=f"Tool '{tool_name}' requires confirmation (risk: {risk_level.value})",
            arguments=redacted_args,
        )

        with self._lock:
            self._pending[permission_id] = pending

        logger.info(
            "Permission required: tool=%s risk=%s permission_id=%s",
            tool_name, risk_level.value, permission_id
        )

        # Emit SSE event
        if self._broadcaster:
            self._broadcaster.broadcast("permission_required", {
                "permission_id": permission_id,
                "tool": tool_name,
                "risk": risk_level.value,
                "reason": pending.reason,
                "arguments": redacted_args,
                "created_at": pending.created_at,
            })

        # Wait for decision with timeout
        event_received = pending.event.wait(timeout=self._timeout_seconds)

        with self._lock:
            self._pending.pop(permission_id, None)

        if not event_received:
            logger.warning(
                "Permission request timed out: permission_id=%s", permission_id
            )
            return False

        decision = pending.decision
        logger.info(
            "Permission decision received: permission_id=%s decision=%s",
            permission_id, decision
        )
        return decision if decision is not None else False

    def check_permission(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        risk_level: Optional[RiskLevel] = None,
    ) -> bool:
        """Convenience method to check permission for a tool execution."""
        from ultron.risk import RiskLevel
        rl = risk_level or RiskLevel.LOW
        if rl in (RiskLevel.READ, RiskLevel.LOW):
            return True
        return self.request_permission(tool_name, rl, arguments or {})

    def decide(self, permission_id: str, allowed: bool) -> bool:
        """Submit a permission decision.

        Called by the web API when user clicks ALLOW or DENY.

        Args:
            permission_id: The ID of the pending permission request
            allowed: True for ALLOW, False for DENY

        Returns:
            True if decision was accepted, False if permission not found
        """
        with self._lock:
            pending = self._pending.get(permission_id)

        if not pending:
            logger.warning(
                "Permission decision for unknown ID: permission_id=%s", permission_id
            )
            return False

        pending.decision = allowed
        pending.event.set()

        # Emit decision event
        if self._broadcaster:
            self._broadcaster.broadcast("permission_decided", {
                "permission_id": permission_id,
                "tool": pending.tool_name,
                "allowed": allowed,
                "decision": "allowed" if allowed else "denied",
            })

        logger.info(
            "Permission %s for tool '%s' (permission_id=%s)",
            "ALLOWED" if allowed else "DENIED", pending.tool_name, permission_id
        )
        return True

    def get_pending(self, permission_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a pending permission request."""
        with self._lock:
            pending = self._pending.get(permission_id)
        if not pending:
            return None
        return {
            "permission_id": pending.permission_id,
            "tool": pending.tool_name,
            "risk": pending.risk_level.value,
            "reason": pending.reason,
            "arguments": pending.arguments,
            "created_at": pending.created_at,
        }

    def list_pending(self) -> list[Dict[str, Any]]:
        """List all pending permission requests."""
        with self._lock:
            return [
                {
                    "permission_id": p.permission_id,
                    "tool": p.tool_name,
                    "risk": p.risk_level.value,
                    "reason": p.reason,
                    "created_at": p.created_at,
                }
                for p in self._pending.values()
            ]

    def clear_expired(self) -> int:
        """Clear expired permission requests. Returns count cleared."""
        import time
        cleared = 0
        now = time.time()
        with self._lock:
            expired_ids = [
                pid for pid, p in self._pending.items()
                if now - p.created_at > self._timeout_seconds
            ]
            for pid in expired_ids:
                self._pending.pop(pid, None)
                cleared += 1
        return cleared


class WebPermissionEngine:
    """PolicyEngine wrapper that uses PermissionManager for CONFIRM actions.

    This allows the orchestrator to use a standard PolicyEngine
    but delegate CONFIRM decisions to the web UI.
    """

    def __init__(
        self,
        policy_engine: Any,
        permission_manager: PermissionManager,
    ) -> None:
        self._policy_engine = policy_engine
        self._permission_manager = permission_manager

    def request_permission(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        arguments: Dict[str, Any] | None = None,
    ) -> bool:
        """Request permission, using web UI for CONFIRM risk levels."""
        from ultron.policy import PolicyAction

        decision = self._policy_engine.evaluate(tool_name, risk_level, arguments)

        if decision.action == PolicyAction.ALLOW:
            return True

        if decision.action == PolicyAction.DENY:
            return False

        # CONFIRM: use web permission manager
        return self._permission_manager.request_permission(
            tool_name, risk_level, arguments or {}
        )


__all__ = [
    "PermissionManager",
    "WebPermissionEngine",
    "PendingPermission",
    "redact_sensitive",
]
