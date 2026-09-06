"""Pipeline — deterministic execution flow for JARVIS requests.

The Pipeline provides a clear, stage-by-stage flow:

  1. Receive request
  2. Create runtime context
  3. Normalize request
  4. Route request
  5. Build plan (if required)
  6. Validate plan
  7. Execute required tools
  8. Collect results
  9. Verify results
  10. Generate final response
  11. Return structured response

The Pipeline is used by the Brain as the inner execution engine.  It does
NOT own memory, conversation history, or user-facing I/O — those remain
in the Brain and CLI layers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.core.agent import Agent, RunResult, ToolEvent
from ultron.core.router import IntentRouter, RouteDecision, RouteType
from ultron.models import (
    ExecutionResult,
    ExecutionStatus,
    Plan,
    PlanStep,
    PlanStepStatus,
    RuntimeContext,
    VerificationResult,
    VerificationStatus,
)
from ultron.tools import ToolExecutor, ToolExecutionResult, ToolExecutionStatus
from ultron.verification import Verifier

logger = logging.getLogger("ultron.pipeline")


@dataclass
class PipelineResult:
    """Structured output of the full pipeline execution."""

    context: RuntimeContext
    text: str
    events: List[ToolEvent] = field(default_factory=list)
    plan: Optional[Plan] = None
    verification: Optional[VerificationResult] = None
    error: Optional[str] = None


class Pipeline:
    """Deterministic execution pipeline for JARVIS requests.

    Encapsulates the full lifecycle from request to verified response,
    without owning conversation memory or user-facing I/O.
    """

    def __init__(
        self,
        agent: Agent,
        router: IntentRouter,
        verifier: Optional[Verifier] = None,
    ) -> None:
        self._agent = agent
        self._router = router
        self._verifier = verifier or Verifier()

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def router(self) -> IntentRouter:
        return self._router

    @property
    def verifier(self) -> Verifier:
        return self._verifier

    def execute(self, user_input: str, context: Optional[RuntimeContext] = None) -> PipelineResult:
        """Run the full pipeline on a user request.

        Returns a PipelineResult with the final text, events, and verification.
        """
        # 1. Create runtime context
        ctx = context or RuntimeContext()

        # 2. Normalize request
        normalized = self._normalize(user_input)
        if not normalized:
            return PipelineResult(
                context=ctx,
                text="Please provide a valid request.",
                error="Empty or whitespace-only user input.",
            )

        # 3. Route request
        decision = self._router.route(normalized)
        ctx.route_type = decision.route_type.value
        ctx.route_target = decision.target
        ctx.route_confidence = decision.confidence

        logger.info(
            "Pipeline route [request_id=%s, route=%s, target=%s, confidence=%.2f]",
            ctx.request_id,
            decision.route_type.value,
            decision.target,
            decision.confidence,
        )

        # 4. Handle unsupported capability
        if decision.route_type == RouteType.UNSUPPORTED:
            msg = f"I cannot perform this action: {decision.reasoning}"
            return PipelineResult(context=ctx, text=msg)

        # 5. Build plan (currently: delegate to agent loop)
        plan = self._build_plan(decision)

        # 6. Execute via agent
        try:
            run_result: RunResult = self._agent.run(normalized)
        except Exception as exc:
            err_type = type(exc).__name__
            logger.error("Pipeline execution failed [request_id=%s]: %s", ctx.request_id, exc)
            return PipelineResult(
                context=ctx,
                text=f"I encountered an error while processing your request ({err_type}: {exc}).",
                plan=plan,
                error=f"{err_type}: {exc}",
            )

        # 7-8. Collect results
        events = run_result.events
        has_limit = any(e.name == "__limit__" for e in events)
        has_errors = any(e.error is not None for e in events)

        # 9. Verify the last meaningful tool execution (if any)
        verification = self._verify_last_execution(events)

        # 10. Determine status
        if has_limit or (has_errors and not run_result.text):
            error_desc = "Tool iteration limit reached" if has_limit else "One or more tool executions failed"
        else:
            error_desc = None

        text_out = run_result.text or "(no response text)"

        # 11. Return structured response
        return PipelineResult(
            context=ctx,
            text=text_out,
            events=events,
            plan=plan,
            verification=verification,
            error=error_desc,
        )

    def _normalize(self, text: str) -> str:
        """Strip and validate the raw user input."""
        if not isinstance(text, str):
            return ""
        return text.strip()

    def _build_plan(self, decision: RouteDecision) -> Plan:
        """Create a plan from the routing decision.

        Phase 1: single-step plans from keyword routing.
        """
        if decision.route_type == RouteType.TOOL and decision.target:
            step = PlanStep(
                tool_name=decision.target,
                description=decision.reasoning,
            )
            return Plan(steps=[step], description=decision.reasoning)

        # For CONVERSATIONAL / AGENT routes, the agent loop handles planning internally
        return Plan(description=decision.reasoning)

    def _verify_last_execution(self, events: List[ToolEvent]) -> Optional[VerificationResult]:
        """Verify the last tool execution event, if any."""
        if not events:
            return None
        # Skip __limit__ pseudo-events
        real_events = [e for e in events if e.name != "__limit__"]
        if not real_events:
            return None

        last = real_events[-1]
        exec_result = ExecutionResult(
            tool_name=last.name,
            status=ExecutionStatus.SUCCESS if last.allowed and not last.error else ExecutionStatus.FAILED,
            output=last.output,
            error=last.error,
            arguments=last.arguments,
        )
        return self._verifier.verify(exec_result)


__all__ = ["Pipeline", "PipelineResult"]
