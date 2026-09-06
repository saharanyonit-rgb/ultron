"""Brain Orchestrator for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

Integrates specialized brains with the existing JARVIS orchestrator.
The BrainOrchestrator:
1. Uses BrainRouter to select the appropriate brain
2. Creates brain-specific providers using BrainProviderFactory
3. Routes tasks through the selected brain
4. Integrates with existing verification
5. Emits SSE events for agent activity
6. Handles agent failures with recovery
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultron.agents import AgentCapability
from ultron.config import Config, BrainModelConfig
from ultron.context import ContextManager
from ultron.llm.base import LLMProvider
from ultron.recovery import RecoveryEngine
from ultron.task import Task, TaskGraph, TaskStatus

logger = logging.getLogger("ultron.brains.orchestrator")


class BrainOrchestrationEvent(str, Enum):
    AGENT_SELECTED = "agent.selected"
    AGENT_STARTED = "agent.started"
    AGENT_PROGRESS = "agent.progress"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"
    REPLAN_STARTED = "replan.started"
    REPLAN_COMPLETED = "replan.completed"


@dataclass
class BrainOrchestrationResult:
    """Result of brain orchestration."""

    success: bool
    brain_type: str
    output: Any
    verification: Any = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BrainContext:
    """Context for brain execution."""

    goal: str
    task: Optional[str] = None
    expected_outcome: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BrainOrchestrator:
    """Orchestrates specialized brain execution.

    The BrainOrchestrator does NOT replace the existing Orchestrator.
    It provides a specialized path for brain-based execution that
    integrates with the existing architecture.
    """

    def __init__(
        self,
        config: Config,
        tools: List[Any],
        tool_executor: Optional[Any] = None,
        event_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        max_agent_transitions: int = 10,
        max_retries: int = 3,
    ) -> None:
        self._config = config
        self._tools = tools
        self._tool_executor = tool_executor
        self._event_handler = event_handler
        self._max_agent_transitions = max_agent_transitions
        self._max_retries = max_retries

        from ultron.brains.provider import BrainProviderFactory
        from ultron.brains.router import BrainRouter, BrainType

        self._provider_factory = BrainProviderFactory(config.llm)
        self._router = BrainRouter()
        self._recovery_engine = RecoveryEngine(max_retries=max_retries)
        self._context_manager = ContextManager()

        self._brains: Dict[str, Any] = {}
        self._execution_id = str(uuid.uuid4())[:12]

    def _get_brain_type_enum(self, brain_type_str: str) -> Any:
        from ultron.brains.router import BrainType
        return BrainType

    def _get_brain_provider(self, brain_type_str: str) -> LLMProvider:
        from ultron.brains.router import BrainType
        model_config = self._get_brain_config(brain_type_str)
        return self._provider_factory.create_provider(model_config)

    def _get_brain_config(self, brain_type_str: str) -> BrainModelConfig:
        brain_map = {
            "planning": self._config.brain.planning,
            "research": self._config.brain.research,
            "coding": self._config.brain.coding,
            "computer": self._config.brain.computer,
            "verification": self._config.brain.verification,
            "fast": self._config.brain.fast,
            "general": self._config.brain.fast,
        }
        return brain_map.get(brain_type_str, self._config.brain.fast)

    def _get_or_create_brain(self, brain_type_str: str) -> Any:
        if brain_type_str not in self._brains:
            provider = self._get_brain_provider(brain_type_str)

            if brain_type_str == "planning":
                from ultron.brains.planning import PlanningBrain
                self._brains[brain_type_str] = PlanningBrain(provider, self._tools, tool_executor=self._tool_executor)
            elif brain_type_str == "research":
                from ultron.brains.research import ResearchBrain
                self._brains[brain_type_str] = ResearchBrain(provider, self._tools, tool_executor=self._tool_executor)
            elif brain_type_str == "coding":
                from ultron.brains.coding import CodingBrain
                self._brains[brain_type_str] = CodingBrain(provider, self._tools, tool_executor=self._tool_executor)
            elif brain_type_str == "computer":
                from ultron.brains.computer import ComputerBrain
                self._brains[brain_type_str] = ComputerBrain(provider, self._tools, tool_executor=self._tool_executor)
            elif brain_type_str == "verification":
                from ultron.brains.verification import VerificationBrain
                self._brains[brain_type_str] = VerificationBrain(provider, self._tools, tool_executor=self._tool_executor)
            else:
                from ultron.brains.research import ResearchBrain
                self._brains[brain_type_str] = ResearchBrain(provider, self._tools, tool_executor=self._tool_executor)

        return self._brains[brain_type_str]

    def execute(
        self,
        goal: str,
        context: Optional[BrainContext] = None,
    ) -> BrainOrchestrationResult:
        """Execute a goal using the appropriate specialized brain.

        Args:
            goal: The user's goal/request
            context: Optional context with task details

        Returns:
            BrainOrchestrationResult with output and verification
        """
        self._emit(BrainOrchestrationEvent.AGENT_STARTED, {
            "goal": goal[:100],
            "execution_id": self._execution_id,
        })

        route_decision = self._router.route(goal)
        brain_type = route_decision.brain_type.value

        self._emit(BrainOrchestrationEvent.AGENT_SELECTED, {
            "brain_type": brain_type,
            "confidence": route_decision.confidence,
            "reasoning": route_decision.reasoning,
        })

        try:
            result = self._execute_brain(brain_type, goal, context)

            from ultron.brains.verification import VerificationStatus

            if result.verification:
                if result.verification.status == VerificationStatus.PASSED:
                    self._emit(BrainOrchestrationEvent.AGENT_COMPLETED, {
                        "brain_type": brain_type,
                        "verification_status": result.verification.status.value,
                    })
                else:
                    self._emit(BrainOrchestrationEvent.AGENT_FAILED, {
                        "brain_type": brain_type,
                        "verification_status": result.verification.status.value,
                        "recommendation": result.verification.recommendation.value,
                    })

            return result

        except Exception as exc:
            logger.error("Brain orchestration failed: %s", exc)
            self._emit(BrainOrchestrationEvent.AGENT_FAILED, {
                "brain_type": brain_type,
                "error": str(exc),
            })
            return BrainOrchestrationResult(
                success=False,
                brain_type=brain_type,
                output=None,
                error=str(exc),
            )

    def _execute_brain(
        self,
        brain_type: str,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute the appropriate brain based on type."""
        brain = self._get_or_create_brain(brain_type)

        if brain_type == "planning":
            return self._execute_planning(brain, goal, context)
        elif brain_type == "research":
            return self._execute_research(brain, goal, context)
        elif brain_type == "coding":
            return self._execute_coding(brain, goal, context)
        elif brain_type == "computer":
            return self._execute_computer(brain, goal, context)
        elif brain_type == "verification":
            return self._execute_verification(brain, goal, context)
        else:
            return self._execute_general(brain, goal, context)

    def _execute_planning(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute planning brain."""
        plan = brain.plan(goal)
        return BrainOrchestrationResult(
            success=True,
            brain_type="planning",
            output=plan.to_dict(),
        )

    def _execute_research(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute research brain."""
        report = brain.research(goal)

        verification = None
        if context and context.expected_outcome:
            verification = self._verify_result(
                goal,
                context.expected_outcome,
                report.to_dict(),
                context.evidence,
            )

        return BrainOrchestrationResult(
            success=True,
            brain_type="research",
            output=report.to_dict(),
            verification=verification,
        )

    def _execute_coding(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute coding brain."""
        result = brain.execute(goal)

        verification = None
        if context and context.expected_outcome:
            verification = self._verify_result(
                goal,
                context.expected_outcome,
                result.to_dict(),
                context.evidence,
            )

        return BrainOrchestrationResult(
            success=True,
            brain_type="coding",
            output=result.to_dict(),
            verification=verification,
        )

    def _execute_computer(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute computer brain."""
        result = brain.execute(goal)

        verification = None
        if context and context.expected_outcome:
            verification = self._verify_result(
                goal,
                context.expected_outcome,
                result.to_dict(),
                context.evidence,
            )

        return BrainOrchestrationResult(
            success=True,
            brain_type="computer",
            output=result.to_dict(),
            verification=verification,
        )

    def _execute_verification(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute verification brain."""
        if not context:
            return BrainOrchestrationResult(
                success=False,
                brain_type="verification",
                output=None,
                error="Verification requires context",
            )

        result = brain.verify(
            task_description=context.task or goal,
            expected_outcome=context.expected_outcome or "",
            actual_result=context.goal,
            evidence=context.evidence,
        )

        return BrainOrchestrationResult(
            success=True,
            brain_type="verification",
            output=result.to_dict(),
            verification=result,
        )

    def _execute_general(
        self,
        brain: Any,
        goal: str,
        context: Optional[BrainContext],
    ) -> BrainOrchestrationResult:
        """Execute general purpose brain (uses research brain)."""
        report = brain.research(goal)
        return BrainOrchestrationResult(
            success=True,
            brain_type="fast",
            output=report.to_dict(),
        )

    def _verify_result(
        self,
        task_description: str,
        expected_outcome: str,
        actual_result: Any,
        evidence: List[str],
    ) -> Any:
        """Verify a result using the verification brain."""
        from ultron.brains.verification import VerificationStatus, VerificationRecommendation

        self._emit(BrainOrchestrationEvent.VERIFICATION_STARTED, {
            "task": task_description[:100],
        })

        verification_brain = self._get_or_create_brain("verification")
        result = verification_brain.verify(
            task_description=task_description,
            expected_outcome=expected_outcome,
            actual_result=actual_result,
            evidence=evidence,
        )

        self._emit(BrainOrchestrationEvent.VERIFICATION_COMPLETED, {
            "status": result.status.value if hasattr(result.status, 'value') else result.status,
            "confidence": result.confidence,
            "recommendation": result.recommendation.value if hasattr(result.recommendation, 'value') else result.recommendation,
        })

        return result

    def execute_plan(
        self,
        plan: Any,
        context: Optional[BrainContext] = None,
    ) -> Dict[str, BrainOrchestrationResult]:
        """Execute a multi-task plan from the Planning Brain.

        Args:
            plan: The execution plan from Planning Brain
            context: Optional shared context

        Returns:
            Dict mapping task_id to result
        """
        from ultron.brains.verification import VerificationRecommendation

        results: Dict[str, BrainOrchestrationResult] = {}
        completed_tasks: set = set()
        agent_transitions = 0

        for group in plan.get_parallel_groups():
            for task in group:
                if agent_transitions >= self._max_agent_transitions:
                    logger.warning("Max agent transitions reached")
                    break

                self._emit(BrainOrchestrationEvent.AGENT_STARTED, {
                    "task_id": task.id,
                    "agent": task.agent,
                    "description": task.description,
                })

                task_context = BrainContext(
                    goal=task.description,
                    task=task.description,
                    metadata=context.metadata if context else {},
                )

                try:
                    brain_type = task.agent if task.agent in ["planning", "research", "coding", "computer", "verification", "fast", "general"] else "fast"
                    result = self.execute(task.description, task_context)

                    results[task.id] = result
                    completed_tasks.add(task.id)
                    agent_transitions += 1

                    if result.success:
                        self._emit(BrainOrchestrationEvent.AGENT_COMPLETED, {
                            "task_id": task.id,
                            "brain_type": result.brain_type,
                        })
                    else:
                        self._emit(BrainOrchestrationEvent.AGENT_FAILED, {
                            "task_id": task.id,
                            "error": result.error,
                        })

                        if result.verification:
                            rec = result.verification.recommendation
                            rec_val = rec.value if hasattr(rec, 'value') else rec
                            if rec_val == VerificationRecommendation.ABORT.value:
                                break

                except Exception as exc:
                    logger.error("Task %s failed: %s", task.id, exc)
                    results[task.id] = BrainOrchestrationResult(
                        success=False,
                        brain_type=task.agent,
                        output=None,
                        error=str(exc),
                    )
                    self._emit(BrainOrchestrationEvent.AGENT_FAILED, {
                        "task_id": task.id,
                        "error": str(exc),
                    })

        return results

    def _emit(self, event: BrainOrchestrationEvent, data: Dict[str, Any]) -> None:
        """Emit an orchestration event."""
        event_data = {
            "event_type": event.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            **data,
        }

        if self._event_handler:
            self._event_handler(event.value, event_data)

        logger.info("Brain event: %s - %s", event.value, data)


__all__ = [
    "BrainOrchestrator",
    "BrainOrchestrationResult",
    "BrainOrchestrationEvent",
    "BrainContext",
]
