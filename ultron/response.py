"""Final Response Engine for JARVIS Phase 5: Autonomous Intelligence.

Generates structured final results after goal execution completes.
Distinguishes SUCCESS, PARTIAL_SUCCESS, FAILED, and BLOCKED outcomes.
Summarizes what was requested, planned, executed, succeeded, and failed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.goal import Goal, GoalStatus
from ultron.task import Task, TaskGraph, TaskStatus

logger = logging.getLogger("ultron.response")


class ResponseOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class TaskSummary:
    """Summary of a single task's execution."""

    task_id: str = ""
    description: str = ""
    status: str = ""
    assigned_agent: Optional[str] = None
    error: Optional[str] = None
    verification_passed: Optional[bool] = None
    duration_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "assigned_agent": self.assigned_agent,
            "error": self.error,
            "verification_passed": self.verification_passed,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class GoalResult:
    """Structured final result of goal execution."""

    goal_id: str = ""
    outcome: ResponseOutcome = ResponseOutcome.FAILED
    summary: str = ""
    detailed_report: str = ""

    original_request: str = ""
    planned_tasks: int = 0
    executed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    blocked_tasks: int = 0

    task_summaries: List[TaskSummary] = field(default_factory=list)
    verification_results: Dict[str, bool] = field(default_factory=dict)

    important_outputs: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "outcome": self.outcome.value,
            "summary": self.summary,
            "detailed_report": self.detailed_report,
            "original_request": self.original_request,
            "planned_tasks": self.planned_tasks,
            "executed_tasks": self.executed_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "blocked_tasks": self.blocked_tasks,
            "task_summaries": [t.to_dict() for t in self.task_summaries],
            "verification_results": self.verification_results,
            "important_outputs": self.important_outputs,
            "limitations": self.limitations,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }


class ResponseEngine:
    """Generates structured final results from goal execution state."""

    def generate(
        self,
        goal: Goal,
        graph: TaskGraph,
        verification_results: Optional[Dict[str, bool]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        limitations: Optional[List[str]] = None,
    ) -> GoalResult:
        """Generate a GoalResult from the current execution state."""
        result = GoalResult(
            goal_id=goal.id,
            original_request=goal.original_request,
            planned_tasks=graph.task_count,
        )

        result.task_summaries = self._summarize_tasks(graph.tasks)
        result.verification_results = verification_results or {}
        result.limitations = limitations or []

        result.executed_tasks = sum(
            1 for t in graph.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
        )
        result.successful_tasks = graph.completed_count
        result.failed_tasks = graph.failed_count
        result.blocked_tasks = len(graph.get_tasks_by_status(TaskStatus.BLOCKED))

        if outputs:
            result.important_outputs = outputs

        result.outcome = self._determine_outcome(result, graph)
        result.summary = self._generate_summary(result)
        result.detailed_report = self._generate_report(result, goal, graph)

        result.completed_at = datetime.now(timezone.utc).isoformat()

        if goal.created_at:
            try:
                start = datetime.fromisoformat(goal.created_at)
                end = datetime.fromisoformat(result.completed_at)
                result.duration_seconds = (end - start).total_seconds()
            except (ValueError, TypeError):
                pass

        logger.info(
            "Goal result [goal_id=%s, outcome=%s, tasks=%d/%d]",
            result.goal_id,
            result.outcome.value,
            result.successful_tasks,
            result.planned_tasks,
        )

        return result

    def _determine_outcome(self, result: GoalResult, graph: TaskGraph) -> ResponseOutcome:
        """Determine the overall outcome from task results."""
        if result.blocked_tasks > 0 and result.successful_tasks == 0:
            return ResponseOutcome.BLOCKED

        if result.failed_tasks > 0 and result.successful_tasks == 0:
            return ResponseOutcome.FAILED

        if result.failed_tasks > 0 and result.successful_tasks > 0:
            return ResponseOutcome.PARTIAL_SUCCESS

        if graph.is_complete and result.failed_tasks == 0:
            return ResponseOutcome.SUCCESS

        if result.executed_tasks == 0:
            return ResponseOutcome.BLOCKED

        return ResponseOutcome.PARTIAL_SUCCESS

    def _summarize_tasks(self, tasks: List[Task]) -> List[TaskSummary]:
        """Create summaries for all tasks."""
        summaries = []
        for task in tasks:
            summary = TaskSummary(
                task_id=task.id,
                description=task.description,
                status=task.status.value,
                assigned_agent=task.assigned_agent,
                error=task.error,
                duration_seconds=task.duration_seconds,
            )

            if task.verification_state:
                summary.verification_passed = task.verification_state == "passed"

            summaries.append(summary)

        return summaries

    def _generate_summary(self, result: GoalResult) -> str:
        """Generate a concise summary."""
        if result.outcome == ResponseOutcome.SUCCESS:
            return (
                f"Goal completed successfully. "
                f"All {result.successful_tasks} tasks executed and verified."
            )

        if result.outcome == ResponseOutcome.PARTIAL_SUCCESS:
            return (
                f"Goal partially completed. "
                f"{result.successful_tasks}/{result.planned_tasks} tasks succeeded, "
                f"{result.failed_tasks} failed."
            )

        if result.outcome == ResponseOutcome.FAILED:
            return (
                f"Goal failed. "
                f"{result.failed_tasks}/{result.planned_tasks} tasks failed."
            )

        if result.outcome == ResponseOutcome.BLOCKED:
            return (
                f"Goal blocked. "
                f"{result.blocked_tasks} tasks blocked, none completed."
            )

        return "Goal execution completed with unknown outcome."

    def _generate_report(self, result: GoalResult, goal: Goal, graph: TaskGraph) -> str:
        """Generate a detailed report."""
        lines = [
            f"## Goal Execution Report",
            f"",
            f"**Request:** {result.original_request}",
            f"**Outcome:** {result.outcome.value.upper()}",
            f"**Duration:** {result.duration_seconds:.1f}s" if result.duration_seconds else "",
            f"",
            f"### Task Summary",
            f"- Planned: {result.planned_tasks}",
            f"- Executed: {result.executed_tasks}",
            f"- Successful: {result.successful_tasks}",
            f"- Failed: {result.failed_tasks}",
            f"- Blocked: {result.blocked_tasks}",
            f"",
        ]

        if result.task_summaries:
            lines.append("### Task Details")
            for ts in result.task_summaries:
                status_icon = "OK" if ts.status == "completed" else "FAIL" if ts.status == "failed" else "BLOCK"
                lines.append(f"- [{status_icon}] {ts.description}")
                if ts.error:
                    lines.append(f"  Error: {ts.error}")
                if ts.verification_passed is not None:
                    lines.append(f"  Verification: {'passed' if ts.verification_passed else 'failed'}")
            lines.append("")

        if result.verification_results:
            lines.append("### Verification Results")
            for task_id, passed in result.verification_results.items():
                lines.append(f"- {task_id}: {'PASSED' if passed else 'FAILED'}")
            lines.append("")

        if result.limitations:
            lines.append("### Limitations")
            for lim in result.limitations:
                lines.append(f"- {lim}")
            lines.append("")

        if result.important_outputs:
            lines.append("### Important Outputs")
            for key, value in result.important_outputs.items():
                lines.append(f"- {key}: {value}")

        return "\n".join(line for line in lines if line is not None)


__all__ = [
    "ResponseOutcome",
    "TaskSummary",
    "GoalResult",
    "ResponseEngine",
]
