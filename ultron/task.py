"""Task Model and Task Graph for JARVIS Phase 5: Autonomous Intelligence.

Provides a dependency-aware task graph that the Planner produces and the
Execution Orchestrator consumes. Supports parallel execution of independent
tasks, dependency validation, cycle detection, and graph serialization.
"""

from __future__ import annotations

import json
import uuid
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("ultron.task")


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Task:
    """A single unit of work within a Goal.

    Supports dependencies, retries, verification, and structured
    input/output.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:10])
    description: str = ""
    objective: str = ""
    status: TaskStatus = TaskStatus.PENDING

    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    assigned_agent: Optional[str] = None
    required_capabilities: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)

    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    retry_count: int = 0
    max_retries: int = 3

    priority: TaskPriority = TaskPriority.NORMAL

    verification_state: Optional[str] = None
    verification_criteria: List[str] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        """Check if the task is in a final state."""
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    @property
    def is_active(self) -> bool:
        """Check if the task is currently executing."""
        return self.status == TaskStatus.RUNNING

    @property
    def can_retry(self) -> bool:
        """Check if the task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration if start and completion times exist."""
        if not self.started_at or not self.completed_at:
            return None
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return None

    def mark_running(self) -> None:
        """Transition task to running state."""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.started_at

    def mark_completed(self, output_data: Optional[Dict[str, Any]] = None) -> None:
        """Transition task to completed state."""
        self.status = TaskStatus.COMPLETED
        if output_data:
            self.output_data = output_data
        self.completed_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.completed_at

    def mark_failed(self, error: str) -> None:
        """Transition task to failed state."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_blocked(self, reason: str) -> None:
        """Transition task to blocked state."""
        self.status = TaskStatus.BLOCKED
        self.error = reason
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_cancelled(self) -> None:
        """Transition task to cancelled state."""
        self.status = TaskStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "objective": self.objective,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "assigned_agent": self.assigned_agent,
            "required_capabilities": self.required_capabilities,
            "required_tools": self.required_tools,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "priority": self.priority.value,
            "verification_state": self.verification_state,
            "verification_criteria": self.verification_criteria,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:10]),
            description=data.get("description", ""),
            objective=data.get("objective", ""),
            status=TaskStatus(data.get("status", "pending")),
            dependencies=data.get("dependencies", []),
            dependents=data.get("dependents", []),
            assigned_agent=data.get("assigned_agent"),
            required_capabilities=data.get("required_capabilities", []),
            required_tools=data.get("required_tools", []),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            priority=TaskPriority(data.get("priority", "normal")),
            verification_state=data.get("verification_state"),
            verification_criteria=data.get("verification_criteria", []),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            updated_at=data.get("updated_at", ""),
            metadata=data.get("metadata", {}),
        )


class TaskGraph:
    """A dependency-aware directed acyclic graph of tasks.

    The Task Graph:
    - Validates dependencies before execution
    - Detects cycles
    - Discovers ready tasks for parallel execution
    - Propagates completion/failure to dependents
    - Supports serialization/deserialization
    """

    def __init__(self, goal_id: str = "", description: str = "") -> None:
        self.goal_id = goal_id
        self.description = description
        self._tasks: Dict[str, Task] = {}
        self._created_at = datetime.now(timezone.utc).isoformat()

    @property
    def tasks(self) -> List[Task]:
        return list(self._tasks.values())

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED)

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)

    @property
    def progress(self) -> float:
        if not self._tasks:
            return 0.0
        return self.completed_count / len(self._tasks)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are in a terminal state."""
        return all(t.is_terminal for t in self._tasks.values())

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    def add_task(self, task: Task) -> None:
        """Add a task to the graph."""
        if task.id in self._tasks:
            raise ValueError(f"Task '{task.id}' already exists in graph")
        self._tasks[task.id] = task
        for dep_id in task.dependencies:
            if dep_id in self._tasks:
                self._tasks[dep_id].dependents.append(task.id)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        """Remove a task and clean up references."""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if dep_task and task_id in dep_task.dependents:
                dep_task.dependents.remove(task_id)

        for dep_id in task.dependents:
            dep_task = self._tasks.get(dep_id)
            if dep_task and task_id in dep_task.dependencies:
                dep_task.dependencies.remove(task_id)

        del self._tasks[task_id]
        return True

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """Add a dependency: task_id depends on depends_on."""
        if task_id not in self._tasks:
            raise ValueError(f"Task '{task_id}' not found")
        if depends_on not in self._tasks:
            raise ValueError(f"Task '{depends_on}' not found")
        if task_id == depends_on:
            raise ValueError("Task cannot depend on itself")

        task = self._tasks[task_id]
        if depends_on not in task.dependencies:
            task.dependencies.append(depends_on)

        dep_task = self._tasks[depends_on]
        if task_id not in dep_task.dependents:
            dep_task.dependents.append(task_id)

    def has_cycle(self) -> bool:
        """Detect cycles using Kahn's algorithm (BFS topological sort)."""
        in_degree: Dict[str, int] = {tid: 0 for tid in self._tasks}
        for task in self._tasks.values():
            for dep in task.dependencies:
                if dep in in_degree:
                    in_degree[task.id] += 1

        queue: deque[str] = deque()
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)

        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            task = self._tasks[node]
            for dep_id in task.dependents:
                if dep_id in in_degree:
                    in_degree[dep_id] -= 1
                    if in_degree[dep_id] == 0:
                        queue.append(dep_id)

        return visited != len(self._tasks)

    def validate(self) -> List[str]:
        """Validate graph structure. Returns list of error messages."""
        errors = []

        if not self._tasks:
            errors.append("Graph has no tasks")
            return errors

        all_ids = set(self._tasks.keys())

        for task in self._tasks.values():
            for dep in task.dependencies:
                if dep not in all_ids:
                    errors.append(f"Task '{task.id}' depends on unknown task '{dep}'")
            for dep in task.dependents:
                if dep not in all_ids:
                    errors.append(f"Task '{task.id}' has unknown dependent '{dep}'")

        if self.has_cycle():
            errors.append("Graph contains circular dependencies")

        return errors

    def ready_tasks(self) -> List[Task]:
        """Return tasks that are PENDING with all dependencies satisfied."""
        completed_ids = {
            tid for tid, t in self._tasks.items()
            if t.status == TaskStatus.COMPLETED
        }

        ready = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            all_deps_met = all(dep in completed_ids for dep in task.dependencies)
            if all_deps_met:
                ready.append(task)

        return ready

    def on_task_completed(self, task_id: str, output_data: Optional[Dict[str, Any]] = None) -> List[Task]:
        """Mark task completed and return newly ready tasks."""
        task = self._tasks.get(task_id)
        if not task:
            return []

        task.mark_completed(output_data)

        newly_ready = []
        for dep_id in task.dependents:
            dep_task = self._tasks.get(dep_id)
            if dep_task and dep_task.status == TaskStatus.PENDING:
                completed_ids = {
                    tid for tid, t in self._tasks.items()
                    if t.status == TaskStatus.COMPLETED
                }
                all_deps_met = all(dep in completed_ids for dep in dep_task.dependencies)
                if all_deps_met:
                    newly_ready.append(dep_task)

        return newly_ready

    def on_task_failed(self, task_id: str, error: str, propagate: bool = True) -> List[str]:
        """Mark task failed and optionally block dependents. Returns blocked task IDs."""
        task = self._tasks.get(task_id)
        if not task:
            return []

        task.mark_failed(error)

        if not propagate:
            return []

        blocked = []
        queue: deque[str] = deque(task.dependents)
        visited: Set[str] = set()

        while queue:
            dep_id = queue.popleft()
            if dep_id in visited:
                continue
            visited.add(dep_id)

            dep_task = self._tasks.get(dep_id)
            if dep_task and not dep_task.is_terminal:
                dep_task.mark_blocked(f"Dependency '{task_id}' failed")
                blocked.append(dep_id)
                queue.extend(dep_task.dependents)

        return blocked

    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        return [t for t in self._tasks.values() if t.status == status]

    def get_parallel_groups(self) -> List[List[Task]]:
        """Return groups of tasks that can execute in parallel at each stage."""
        if not self._tasks:
            return []

        groups = []
        remaining = set(self._tasks.keys())
        completed: Set[str] = set()

        max_iterations = len(self._tasks) + 1
        iteration = 0

        while remaining and iteration < max_iterations:
            iteration += 1
            group = []
            for tid in list(remaining):
                task = self._tasks[tid]
                all_deps_met = all(dep in completed for dep in task.dependencies)
                if all_deps_met:
                    group.append(task)

            if not group:
                break

            groups.append(group)
            for task in group:
                completed.add(task.id)
                remaining.discard(task.id)

        return groups

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "created_at": self._created_at,
            "tasks": [t.to_dict() for t in self._tasks.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskGraph":
        graph = cls(
            goal_id=data.get("goal_id", ""),
            description=data.get("description", ""),
        )
        graph._created_at = data.get("created_at", graph._created_at)
        for task_data in data.get("tasks", []):
            graph.add_task(Task.from_dict(task_data))
        return graph

    def serialize(self) -> str:
        """Serialize graph to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def deserialize(cls, data: str) -> "TaskGraph":
        """Deserialize graph from JSON string."""
        return cls.from_dict(json.loads(data))

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the graph state."""
        status_counts = {}
        for task in self._tasks.values():
            status = task.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "goal_id": self.goal_id,
            "total_tasks": self.task_count,
            "progress": self.progress,
            "status_counts": status_counts,
            "is_complete": self.is_complete,
            "has_failures": self.has_failures,
        }


__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "TaskGraph",
]
