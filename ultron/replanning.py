"""Dynamic Replanning for JARVIS Phase 5.

Automatically detects when a plan needs revision due to failures,
new information, or changing conditions, and triggers replanning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.llm.base import LLMProvider, ProviderResult
from ultron.models import ExecutionResult, ExecutionStatus, MultiStepPlan, MultiStepPlanStep
from ultron.orchestrator import Orchestrator

logger = logging.getLogger("ultron.replanning")


@dataclass
class ReplanTrigger:
    """Information about why replanning was triggered."""
    reason: str = ""
    failed_tasks: List[str] = field(default_factory=list)
    partial_results: Dict[str, Any] = field(default_factory=dict)
    new_constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "failed_tasks": self.failed_tasks,
            "partial_results": self.partial_results,
            "new_constraints": self.new_constraints,
        }


@dataclass
class ReplanResult:
    """Result of a replanning attempt."""
    success: bool = False
    new_plan: Optional[MultiStepPlan] = None
    changes: List[str] = field(default_factory=list)
    reasoning: str = ""
    preserved_tasks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "changes": self.changes,
            "reasoning": self.reasoning,
            "preserved_tasks": self.preserved_tasks,
            "new_plan_steps": len(self.new_plan.steps) if self.new_plan else 0,
        }


class DynamicReplanner:
    """Detects plan failures and triggers intelligent replanning.

    Integrates with the orchestrator and LLM to produce revised plans
    that preserve successful progress while replacing failed steps.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        max_replans: int = 3,
        failure_threshold: int = 1,
    ) -> None:
        self._provider = provider
        self._max_replans = max_replans
        self._failure_threshold = failure_threshold
        self._replan_count = 0

    @property
    def replan_count(self) -> int:
        return self._replan_count

    def should_replan(
        self,
        results: Dict[str, ExecutionResult],
        total_tasks: int,
    ) -> ReplanTrigger:
        """Determine if replanning is needed based on execution results."""
        failed = [
            tid for tid, r in results.items()
            if r.status == ExecutionStatus.FAILED
        ]

        if len(failed) >= self._failure_threshold:
            return ReplanTrigger(
                reason=f"{len(failed)} tasks failed",
                failed_tasks=failed,
                partial_results={
                    tid: r.output for tid, r in results.items()
                    if r.status == ExecutionStatus.SUCCESS
                },
            )

        return ReplanTrigger(reason="no_replan_needed")

    def replan(
        self,
        original_plan: MultiStepPlan,
        trigger: ReplanTrigger,
        objective: str,
        results: Optional[Dict[str, ExecutionResult]] = None,
    ) -> ReplanResult:
        """Create a revised plan based on trigger information."""
        if self._replan_count >= self._max_replans:
            return ReplanResult(
                success=False,
                reasoning=f"Max replans ({self._max_replans}) reached",
            )

        self._replan_count += 1

        if trigger.reason == "no_replan_needed":
            return ReplanResult(
                success=True,
                new_plan=original_plan,
                reasoning="No replanning needed",
            )

        if self._provider:
            return self._llm_replan(original_plan, trigger, objective, results or {})

        return self._heuristic_replan(original_plan, trigger, results or {})

    def _llm_replan(
        self,
        original_plan: MultiStepPlan,
        trigger: ReplanTrigger,
        objective: str,
        results: Dict[str, ExecutionResult],
    ) -> ReplanResult:
        """Use LLM to generate a revised plan."""
        original_tasks = []
        for step in original_plan.steps:
            original_tasks.append({
                "task_id": step.step_id,
                "tool": step.tool_name,
                "description": step.description,
                "depends_on": step.dependencies,
            })

        completed = {
            tid: r.output for tid, r in results.items()
            if r.status == ExecutionStatus.SUCCESS
        }

        prompt = (
            f"Replan this task sequence after failures.\n\n"
            f"Objective: {objective}\n"
            f"Original plan: {json.dumps(original_tasks, default=str)[:2000]}\n"
            f"Failed tasks: {trigger.failed_tasks}\n"
            f"Completed: {json.dumps(completed, default=str)[:1000]}\n"
            f"Reason: {trigger.reason}\n\n"
            "Create a revised plan that:\n"
            "1. Preserves completed steps\n"
            "2. Replaces failed steps with alternatives\n"
            "3. Maintains dependency ordering\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"steps": [{"task_id": "...", "tool": "...", "description": "...", "depends_on": []}], "reasoning": "...", "changes": ["..."]}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_plan_response(result.text, trigger)
        except Exception as exc:
            logger.warning("LLM replanning failed: %s", exc)

        return self._heuristic_replan(original_plan, trigger, results)

    def _heuristic_replan(
        self,
        original_plan: MultiStepPlan,
        trigger: ReplanTrigger,
        results: Dict[str, ExecutionResult],
    ) -> ReplanResult:
        """Heuristic-based replanning as fallback."""
        new_steps = []
        changes = []

        for step in original_plan.steps:
            if step.step_id in trigger.failed_tasks:
                changes.append(f"Removed failed task: {step.step_id}")
                continue
            if step.step_id in results and results[step.step_id].status == ExecutionStatus.SUCCESS:
                changes.append(f"Kept completed task: {step.step_id}")
            new_steps.append(step)

        if not new_steps:
            changes.append("All steps were removed, keeping original plan")
            new_steps = list(original_plan.steps)

        new_plan = MultiStepPlan(
            description=original_plan.description,
            steps=new_steps,
        )

        return ReplanResult(
            success=True,
            new_plan=new_plan,
            changes=changes,
            reasoning="Heuristic replanning: removed failed steps",
        )

    def _parse_plan_response(
        self,
        text: str,
        trigger: ReplanTrigger,
    ) -> ReplanResult:
        """Parse LLM replanning response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                steps = []
                for s in data.get("steps", []):
                    if isinstance(s, dict):
                        steps.append(MultiStepPlanStep(
                            step_id=s.get("task_id", f"replan_{len(steps)}"),
                            tool_name=s.get("tool", "unknown"),
                            description=s.get("description", ""),
                            arguments=s.get("parameters", {}),
                            dependencies=s.get("depends_on", []),
                        ))

                return ReplanResult(
                    success=True,
                    new_plan=MultiStepPlan(
                        description="",
                        steps=steps,
                    ),
                    changes=data.get("changes", []),
                    reasoning=data.get("reasoning", "LLM replanning"),
                    preserved_tasks=[s.step_id for s in steps],
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return ReplanResult(
            success=False,
            reasoning="Failed to parse LLM replanning response",
        )

    def reset(self) -> None:
        """Reset replan counter."""
        self._replan_count = 0


__all__ = [
    "ReplanTrigger",
    "ReplanResult",
    "DynamicReplanner",
]
