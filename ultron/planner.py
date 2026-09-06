"""Multi-step planner with dependency management and retry support.

Plans have steps with explicit dependencies. The PlanExecutor executes
steps in dependency order, handling retries and failures.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ultron.models import (
    ExecutionResult,
    ExecutionStatus,
    MultiStepPlan,
    MultiStepPlanStep,
    PlanStepPriority,
    PlanStepStatus,
)

logger = logging.getLogger("ultron.planner")


class PlanValidationError(Exception):
    """Raised when a plan has structural errors."""


class Planner:
    """Creates and validates multi-step plans."""

    def __init__(self, max_steps: int = 20) -> None:
        self._max_steps = max_steps

    def create_plan(
        self,
        steps: List[MultiStepPlanStep],
        description: str = "",
    ) -> MultiStepPlan:
        """Create and validate a multi-step plan."""
        if not steps:
            raise PlanValidationError("Plan must have at least one step")

        if len(steps) > self._max_steps:
            raise PlanValidationError(
                f"Plan has {len(steps)} steps, maximum is {self._max_steps}"
            )

        plan = MultiStepPlan(
            steps=steps,
            description=description,
            max_steps=self._max_steps,
        )

        if plan.has_cycle():
            raise PlanValidationError("Plan has circular dependencies")

        step_ids = {s.step_id for s in steps}
        for step in steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    raise PlanValidationError(
                        f"Step {step.step_id} depends on unknown step {dep}"
                    )

        return plan


class PlanExecutor:
    """Executes multi-step plans with dependency ordering."""

    def __init__(
        self,
        tool_executor: Callable[[str, Dict[str, Any]], ExecutionResult],
    ) -> None:
        self._tool_executor = tool_executor

    def execute_plan(self, plan: MultiStepPlan) -> MultiStepPlan:
        """Execute all ready steps in the plan. Returns updated plan."""
        max_iterations = plan.max_steps * 2
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            ready = plan.ready_steps()
            if not ready:
                break

            for step in ready:
                self._execute_step(step)

            if not plan.pending_steps() and not plan.failed_steps():
                break

        return plan

    def _execute_step(self, step: MultiStepPlanStep) -> None:
        """Execute a single plan step."""
        step.status = PlanStepStatus.RUNNING
        logger.info("Executing step %s: %s", step.step_id, step.objective)

        try:
            result = self._tool_executor(step.tool_name, step.arguments)
            step.result = result

            if result.status == ExecutionStatus.SUCCESS:
                step.status = PlanStepStatus.SUCCEEDED
            else:
                step.status = PlanStepStatus.FAILED
                step.retry_count += 1
                logger.warning(
                    "Step %s failed: %s (retry %d/%d)",
                    step.step_id,
                    result.error,
                    step.retry_count,
                    step.max_retries,
                )
        except Exception as exc:
            step.status = PlanStepStatus.FAILED
            step.retry_count += 1
            logger.error("Step %s exception: %s", step.step_id, exc)


__all__ = ["Planner", "PlanExecutor", "PlanValidationError"]
