"""Execution state persistence for JARVIS Phase 4.

Preserves task execution state across interruptions:
  - Task ID
  - Plan ID
  - Current step
  - Completed steps
  - Failed steps
  - Execution results
  - Verification results
  - Timestamps
  - Retry count
  - Final status

This allows recovery from interrupted tasks rather than starting over.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.execution_state")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class StepState:
    """State of a single execution step."""

    step_id: str
    objective: str = ""
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskState:
    """Complete state of a task execution."""

    task_id: str
    plan_id: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    steps: List[StepState] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "description": self.description,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskState":
        steps = [StepState.from_dict(s) for s in data.get("steps", [])]
        return cls(
            task_id=data["task_id"],
            plan_id=data.get("plan_id", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            steps=steps,
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_at=data.get("completed_at"),
        )

    @property
    def completed_steps(self) -> List[StepState]:
        return [s for s in self.steps if s.status == "succeeded"]

    @property
    def failed_steps(self) -> List[StepState]:
        return [s for s in self.steps if s.status == "failed"]

    @property
    def pending_steps(self) -> List[StepState]:
        return [s for s in self.steps if s.status == "pending"]

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        return len(self.completed_steps) / len(self.steps)


class ExecutionStateStore:
    """Persists task execution state to disk."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, TaskState] = {}
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def save_task(self, task: TaskState) -> None:
        """Save or update a task state."""
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._tasks[task.task_id] = task
        self._persist()

    def load_task(self, task_id: str) -> Optional[TaskState]:
        """Load a task by ID."""
        return self._tasks.get(task_id)

    def list_tasks(self, status: TaskStatus | None = None) -> List[TaskState]:
        """List all tasks, optionally filtered by status."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._persist()
            return True
        return False

    def update_step(
        self,
        task_id: str,
        step_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update a specific step in a task."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        for step in task.steps:
            if step.step_id == step_id:
                step.status = status
                step.result = result
                step.error = error
                if status == "running":
                    step.started_at = datetime.now(timezone.utc).isoformat()
                elif status in ("succeeded", "failed"):
                    step.completed_at = datetime.now(timezone.utc).isoformat()
                self._persist()
                return True
        return False

    def get_incomplete_tasks(self) -> List[TaskState]:
        """Get tasks that were interrupted (running or paused)."""
        return self.list_tasks(TaskStatus.RUNNING) + self.list_tasks(TaskStatus.PAUSED)

    def _load(self) -> None:
        """Load state from disk."""
        if not self._path.is_file():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                for task_data in data.get("tasks", []):
                    task = TaskState.from_dict(task_data)
                    self._tasks[task.task_id] = task
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load execution state: %s", exc)

    def _persist(self) -> None:
        """Persist state to disk."""
        data = {
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to persist execution state: %s", exc)


__all__ = ["TaskStatus", "StepState", "TaskState", "ExecutionStateStore"]
