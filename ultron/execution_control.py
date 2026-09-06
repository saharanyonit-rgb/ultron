"""Execution Control for JARVIS Phase 5.

Provides kill-switch, pause/resume, rate limiting, and execution gating
for safe autonomous operation.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ultron.execution_control")


class ExecutionState(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    RATE_LIMITED = "rate_limited"


@dataclass
class ExecutionGate:
    """Gate that controls whether execution can proceed."""
    name: str = ""
    enabled: bool = True
    reason: str = ""
    check_fn: Optional[Callable[[], bool]] = None

    def can_proceed(self) -> bool:
        if not self.enabled:
            return True
        if self.check_fn:
            return self.check_fn()
        return True


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_per_minute: int = 30
    max_per_hour: int = 500
    burst_limit: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_per_minute": self.max_per_minute,
            "max_per_hour": self.max_per_hour,
            "burst_limit": self.burst_limit,
        }


class ExecutionController:
    """Controls and monitors autonomous execution.

    Features:
    - Kill-switch to immediately halt all operations
    - Pause/resume with state preservation
    - Rate limiting to prevent API abuse
    - Custom gates for conditional execution
    """

    def __init__(
        self,
        rate_limit: Optional[RateLimitConfig] = None,
    ) -> None:
        self._state = ExecutionState.RUNNING
        self._rate_config = rate_limit or RateLimitConfig()
        self._gates: Dict[str, ExecutionGate] = {}
        self._call_times: List[float] = []
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._listeners: List[Callable[[ExecutionState], None]] = []

    @property
    def state(self) -> ExecutionState:
        return self._state

    def add_listener(self, listener: Callable[[ExecutionState], None]) -> None:
        """Add a state change listener."""
        self._listeners.append(listener)

    def kill(self) -> None:
        """Emergency stop - immediately halts all execution."""
        self._set_state(ExecutionState.STOPPED)
        self._pause_event.set()
        logger.critical("KILL SWITCH ACTIVATED")

    def pause(self) -> None:
        """Pause execution gracefully."""
        if self._state != ExecutionState.STOPPED:
            self._set_state(ExecutionState.PAUSED)
            self._pause_event.clear()
            logger.info("Execution paused")

    def resume(self) -> None:
        """Resume paused execution."""
        if self._state == ExecutionState.PAUSED:
            self._set_state(ExecutionState.RUNNING)
            self._pause_event.set()
            logger.info("Execution resumed")

    def wait_if_paused(self, timeout: float = 1.0) -> bool:
        """Block if paused, return True if resumed, False if timed out."""
        if self._state == ExecutionState.STOPPED:
            return False
        return self._pause_event.wait(timeout=timeout)

    def can_execute(self) -> bool:
        """Check if execution is allowed (not killed/paused, within rate limits)."""
        if self._state == ExecutionState.STOPPED:
            return False
        if self._state == ExecutionState.PAUSED:
            self.wait_if_paused(timeout=0.1)
            if self._state == ExecutionState.STOPPED:
                return False

        for gate in self._gates.values():
            if not gate.can_proceed():
                logger.debug("Gate '%s' blocked execution: %s", gate.name, gate.reason)
                return False

        if not self._check_rate_limit():
            return False

        return True

    def record_execution(self) -> None:
        """Record that an execution happened (for rate limiting)."""
        now = time.time()
        with self._lock:
            self._call_times.append(now)
            self._call_times = [
                t for t in self._call_times if now - t < 3600
            ]

    def add_gate(self, gate: ExecutionGate) -> None:
        """Add an execution gate."""
        self._gates[gate.name] = gate

    def remove_gate(self, name: str) -> None:
        """Remove an execution gate."""
        self._gates.pop(name, None)

    def get_rate_status(self) -> Dict[str, Any]:
        """Get current rate limiting status."""
        now = time.time()
        with self._lock:
            recent_minute = sum(
                1 for t in self._call_times if now - t < 60
            )
            recent_hour = sum(
                1 for t in self._call_times if now - t < 3600
            )
        return {
            "per_minute": recent_minute,
            "per_hour": recent_hour,
            "limit_minute": self._rate_config.max_per_minute,
            "limit_hour": self._rate_config.max_per_hour,
        }

    def reset(self) -> None:
        """Reset to running state."""
        self._set_state(ExecutionState.RUNNING)
        self._call_times.clear()
        self._pause_event.set()

    def _check_rate_limit(self) -> bool:
        """Check if rate limits allow another execution."""
        now = time.time()
        with self._lock:
            recent_minute = sum(
                1 for t in self._call_times if now - t < 60
            )
            if recent_minute >= self._rate_config.max_per_minute:
                self._set_state(ExecutionState.RATE_LIMITED)
                logger.warning("Rate limit hit: %d/min", recent_minute)
                return False

            recent_burst = sum(
                1 for t in self._call_times if now - t < 10
            )
            if recent_burst >= self._rate_config.burst_limit:
                logger.warning("Burst limit hit: %d/10s", recent_burst)
                return False

        if self._state == ExecutionState.RATE_LIMITED:
            self._set_state(ExecutionState.RUNNING)
        return True

    def _set_state(self, new_state: ExecutionState) -> None:
        old = self._state
        self._state = new_state
        if old != new_state:
            for listener in self._listeners:
                try:
                    listener(new_state)
                except Exception as exc:
                    logger.error("State listener error: %s", exc)


__all__ = [
    "ExecutionState",
    "ExecutionGate",
    "RateLimitConfig",
    "ExecutionController",
]
