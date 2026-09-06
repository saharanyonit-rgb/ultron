"""Multi-Goal Management for JARVIS Phase 5.

Manages concurrent goal execution with prioritization, dependency
tracking, and resource allocation across goals.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultron.goal import Goal, GoalStatus

logger = logging.getLogger("ultron.multi_goal")


class GoalPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class GoalScheduleStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class GoalSlot:
    """Scheduled goal with priority and resource allocation."""
    goal: Goal = field(default_factory=Goal)
    priority: str = GoalPriority.NORMAL.value
    schedule_status: str = GoalScheduleStatus.PENDING.value
    allocated_budget: Dict[str, float] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal.id,
            "description": self.goal.description,
            "priority": self.priority,
            "schedule_status": self.schedule_status,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
        }


class MultiGoalManager:
    """Manages multiple concurrent goals with prioritization.

    Features:
    - Priority-based scheduling
    - Dependency resolution between goals
    - Resource allocation per goal
    - Status tracking and reporting
    """

    def __init__(self, max_concurrent: int = 3) -> None:
        self._max_concurrent = max_concurrent
        self._slots: Dict[str, GoalSlot] = {}
        self._completion_callbacks: List[Callable[[GoalSlot], None]] = []

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def add_goal(
        self,
        goal: Goal,
        priority: str = GoalPriority.NORMAL.value,
        depends_on: Optional[List[str]] = None,
        budget: Optional[Dict[str, float]] = None,
    ) -> GoalSlot:
        """Add a goal to the queue."""
        slot = GoalSlot(
            goal=goal,
            priority=priority,
            depends_on=depends_on or [],
            allocated_budget=budget or {},
        )
        self._slots[goal.id] = slot
        return slot

    def remove_goal(self, goal_id: str) -> bool:
        """Remove a goal from management."""
        slot = self._slots.pop(goal_id, None)
        if slot:
            slot.schedule_status = GoalScheduleStatus.CANCELLED.value
            return True
        return False

    def start_goal(self, goal_id: str) -> bool:
        """Mark a goal as running."""
        slot = self._slots.get(goal_id)
        if not slot:
            return False

        if not self._can_start(slot):
            return False

        slot.schedule_status = GoalScheduleStatus.RUNNING.value
        slot.started_at = time.time()
        return True

    def complete_goal(
        self,
        goal_id: str,
        success: bool = True,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a goal as completed."""
        slot = self._slots.get(goal_id)
        if not slot:
            return False

        slot.schedule_status = (
            GoalScheduleStatus.COMPLETED.value if success
            else GoalScheduleStatus.FAILED.value
        )
        slot.completed_at = time.time()
        slot.result = result

        for callback in self._completion_callbacks:
            try:
                callback(slot)
            except Exception as exc:
                logger.error("Completion callback error: %s", exc)

        return True

    def pause_goal(self, goal_id: str) -> bool:
        slot = self._slots.get(goal_id)
        if slot and slot.schedule_status == GoalScheduleStatus.RUNNING.value:
            slot.schedule_status = GoalScheduleStatus.PAUSED.value
            return True
        return False

    def resume_goal(self, goal_id: str) -> bool:
        slot = self._slots.get(goal_id)
        if slot and slot.schedule_status == GoalScheduleStatus.PAUSED.value:
            slot.schedule_status = GoalScheduleStatus.RUNNING.value
            return True
        return False

    def get_next_goal(self) -> Optional[GoalSlot]:
        """Get the highest priority pending goal that can run."""
        pending = [
            slot for slot in self._slots.values()
            if slot.schedule_status == GoalScheduleStatus.PENDING.value
        ]

        priority_order = {
            GoalPriority.CRITICAL.value: 0,
            GoalPriority.HIGH.value: 1,
            GoalPriority.NORMAL.value: 2,
            GoalPriority.LOW.value: 3,
        }

        pending.sort(
            key=lambda s: priority_order.get(s.priority, 99)
        )

        for slot in pending:
            if self._can_start(slot):
                return slot

        return None

    def get_running_count(self) -> int:
        return sum(
            1 for s in self._slots.values()
            if s.schedule_status == GoalScheduleStatus.RUNNING.value
        )

    def get_all_goals(self) -> List[GoalSlot]:
        return list(self._slots.values())

    def get_goals_by_status(self, status: str) -> List[GoalSlot]:
        return [
            s for s in self._slots.values()
            if s.schedule_status == status
        ]

    def add_completion_callback(self, callback: Callable[[GoalSlot], None]) -> None:
        self._completion_callbacks.append(callback)

    def get_summary(self) -> Dict[str, Any]:
        status_counts: Dict[str, int] = {}
        for slot in self._slots.values():
            status_counts[slot.schedule_status] = status_counts.get(slot.schedule_status, 0) + 1
        return {
            "total": len(self._slots),
            "by_status": status_counts,
            "running": self.get_running_count(),
            "max_concurrent": self._max_concurrent,
        }

    def _can_start(self, slot: GoalSlot) -> bool:
        if self.get_running_count() >= self._max_concurrent:
            return False
        for dep_id in slot.depends_on:
            dep_slot = self._slots.get(dep_id)
            if not dep_slot or dep_slot.schedule_status != GoalScheduleStatus.COMPLETED.value:
                return False
        return True


__all__ = [
    "GoalPriority",
    "GoalScheduleStatus",
    "GoalSlot",
    "MultiGoalManager",
]
