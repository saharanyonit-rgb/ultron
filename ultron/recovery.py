"""Recovery and replanning for JARVIS Phase 4.

Handles execution failures with controlled recovery:
  - Error classification
  - Retryable error detection
  - Maximum retry limits
  - Previous result preservation
  - Replanning on failure
  - Infinite loop prevention
  - Recovery decision recording
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultron.execution_state import StepState, TaskState, TaskStatus
from ultron.models import ExecutionResult, ExecutionStatus

logger = logging.getLogger("ultron.recovery")


class RecoveryAction(str, Enum):
    RETRY = "retry"
    REPLAN = "replan"
    SKIP = "skip"
    ABORT = "abort"


class ErrorClass(str, Enum):
    TRANSIENT = "transient"  # Network timeout, temporary resource issue
    PERMANENT = "permanent"  # Invalid input, missing resource
    RECOVERABLE = "recoverable"  # Can be retried or replanned
    FATAL = "fatal"  # Cannot recover


# Map error types to error classes
ERROR_CLASS_MAP: Dict[str, ErrorClass] = {
    "TimeoutError": ErrorClass.TRANSIENT,
    "ConnectionError": ErrorClass.TRANSIENT,
    "RateLimitError": ErrorClass.TRANSIENT,
    "FileNotFoundError": ErrorClass.PERMANENT,
    "PermissionError": ErrorClass.PERMANENT,
    "ValueError": ErrorClass.PERMANENT,
    "ToolExecutionError": ErrorClass.RECOVERABLE,
    "RuntimeError": ErrorClass.RECOVERABLE,
}


@dataclass
class RecoveryDecision:
    """Decision made during recovery."""

    action: RecoveryAction
    reason: str
    error_class: ErrorClass
    retry_count: int
    max_retries: int
    previous_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "error_class": self.error_class.value,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class RecoveryEngine:
    """Handles execution failures with controlled recovery."""

    def __init__(
        self,
        max_retries: int = 3,
        retryable_errors: List[str] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._retryable_errors = retryable_errors or [
            "TimeoutError",
            "ConnectionError",
            "RateLimitError",
            "ToolExecutionError",
        ]
        self._decisions: List[RecoveryDecision] = []

    @property
    def decisions(self) -> List[RecoveryDecision]:
        return list(self._decisions)

    def classify_error(self, error: Exception | str) -> ErrorClass:
        """Classify an error by its recovery potential."""
        error_type = type(error).__name__ if isinstance(error, Exception) else str(error)

        if error_type in ERROR_CLASS_MAP:
            return ERROR_CLASS_MAP[error_type]

        # Check if it's a known retryable error
        for retryable in self._retryable_errors:
            if retryable in error_type:
                return ErrorClass.RECOVERABLE

        return ErrorClass.PERMANENT

    def decide_recovery(
        self,
        step: StepState,
        error: Exception | str,
        previous_results: List[Dict[str, Any]] | None = None,
    ) -> RecoveryDecision:
        """Decide how to recover from a step failure."""
        error_class = self.classify_error(error)
        retry_count = step.retry_count

        # Check retry limit
        if retry_count >= self._max_retries:
            decision = RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason=f"Retry limit reached ({retry_count}/{self._max_retries})",
                error_class=error_class,
                retry_count=retry_count,
                max_retries=self._max_retries,
                previous_results=previous_results or [],
            )
            self._decisions.append(decision)
            return decision

        # Decide based on error class
        if error_class == ErrorClass.FATAL:
            action = RecoveryAction.ABORT
            reason = f"Fatal error: {error}"
        elif error_class == ErrorClass.PERMANENT:
            action = RecoveryAction.SKIP
            reason = f"Permanent error, skipping: {error}"
        elif error_class in (ErrorClass.TRANSIENT, ErrorClass.RECOVERABLE):
            action = RecoveryAction.RETRY
            reason = f"Retryable error ({error_class.value}): {error}"
        else:
            action = RecoveryAction.ABORT
            reason = f"Unknown error class: {error_class}"

        decision = RecoveryDecision(
            action=action,
            reason=reason,
            error_class=error_class,
            retry_count=retry_count,
            max_retries=self._max_retries,
            previous_results=previous_results or [],
        )
        self._decisions.append(decision)
        return decision

    def should_retry(self, step: StepState, error: Exception | str) -> bool:
        """Quick check: should we retry this step?"""
        decision = self.decide_recovery(step, error)
        return decision.action == RecoveryAction.RETRY

    def should_replan(self, step: StepState, error: Exception | str) -> bool:
        """Quick check: should we replan?"""
        decision = self.decide_recovery(step, error)
        return decision.action == RecoveryAction.REPLAN

    def execute_recovery(
        self,
        task: TaskState,
        failed_step: StepState,
        error: Exception | str,
        replan_callback: Callable[[TaskState, StepState], Optional[TaskState]] | None = None,
    ) -> Optional[TaskState]:
        """Execute a recovery action. Returns new task if replanned."""
        decision = self.decide_recovery(failed_step, error)

        if decision.action == RecoveryAction.RETRY:
            failed_step.retry_count += 1
            failed_step.status = "pending"
            logger.info("Retrying step %s (attempt %d)", failed_step.step_id, failed_step.retry_count)
            return task

        elif decision.action == RecoveryAction.REPLAN:
            if replan_callback:
                new_task = replan_callback(task, failed_step)
                if new_task:
                    logger.info("Replanned task %s → %s", task.task_id, new_task.task_id)
                    return new_task
            # If no replan callback or replan failed, abort
            decision.action = RecoveryAction.ABORT
            decision.reason += " (replan not available)"

        elif decision.action == RecoveryAction.SKIP:
            failed_step.status = "skipped"
            logger.info("Skipped step %s", failed_step.step_id)
            return task

        # ABORT
        task.status = TaskStatus.FAILED
        logger.warning("Aborted task %s: %s", task.task_id, decision.reason)
        return task


# Alias for backward compatibility
RecoveryManager = RecoveryEngine

__all__ = [
    "RecoveryAction",
    "ErrorClass",
    "RecoveryDecision",
    "RecoveryEngine",
    "RecoveryManager",
    "ERROR_CLASS_MAP",
]
