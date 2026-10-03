"""Datatypes, Configuration, and States for Phase 5 Orchestrator.

Decouples dataclasses and state Enums from main execution loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ultron.response import GoalResult


class OrchestratorState(StrEnum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    SHUTTING_DOWN = "shutting_down"


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    max_concurrent_tasks: int = 3
    max_retries: int = 3
    enable_verification: bool = True
    enable_persistence: bool = True
    enable_parallel_execution: bool = True
    command_timeout: int = 30


@dataclass
class OrchestratorResult:
    """Result of an orchestration run."""

    goal_result: GoalResult
    state: OrchestratorState = OrchestratorState.COMPLETED
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_result": self.goal_result.to_dict(),
            "state": self.state.value,
            "events_count": len(self.events),
        }


__all__ = [
    "OrchestratorState",
    "OrchestratorConfig",
    "OrchestratorResult",
]
