"""JARVIS Core Brain / Orchestrator for Ultron.

The central orchestration layer that receives user requests, validates input,
coordinates execution across LLM providers, tool registries, intent routers, and agent loops,
handles errors safely, and returns structured responses.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.core.agent import Agent, RunResult, ToolEvent
from ultron.core.router import IntentRouter, RouteDecision, RouteType
from ultron.memory import Memory
from ultron.pipeline import Pipeline, PipelineResult

logger = logging.getLogger("ultron.brain")

_SECRET_PATTERNS = [
    re.compile(r"(API_KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(sk-or-v1-|nvapi-|gsk_|sk-|pk-)\S+", re.IGNORECASE),
]


def _sanitize_error(msg: str) -> str:
    """Remove potential secrets from error messages before user exposure."""
    sanitized = msg
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1=[REDACTED]", sanitized)
    return sanitized


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class BrainError(Exception):
    """Base exception for orchestrator errors."""


class InvalidRequestError(BrainError):
    """Raised when a request payload is invalid."""


@dataclass
class UserRequest:
    """Strongly typed input request model for the Brain."""

    user_input: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrainResponse:
    """Strongly typed response model returned by the Brain."""

    request_id: str
    response: str
    status: ResponseStatus
    error: Optional[str] = None
    events: List[ToolEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class Brain:
    """Central Orchestrator for JARVIS / Ultron.

    Coordinates execution flow:
    Request Validation -> Context Setup -> Intent Routing -> Component Delegation -> Response Assembly
    """

    def __init__(
        self,
        agent: Agent,
        memory: Optional[Memory] = None,
        router: Optional[IntentRouter] = None,
        pipeline: Optional[Pipeline] = None,
    ) -> None:
        self._agent = agent
        self._memory = memory
        self._router = router or IntentRouter(
            tools=list(agent._tools.values()),
            provider=agent._provider,
        )
        self._pipeline = pipeline or Pipeline(
            agent=agent,
            router=self._router,
        )

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def memory(self) -> Optional[Memory]:
        return self._memory

    @property
    def router(self) -> IntentRouter:
        return self._router

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline

    def process(self, request: UserRequest | str) -> BrainResponse:
        """Process a user request through the orchestration lifecycle."""
        if isinstance(request, str):
            req = UserRequest(user_input=request)
        else:
            req = request

        request_id = req.request_id
        logger.info("Request received [request_id=%s, input_len=%d]", request_id, len(req.user_input or ""))

        # 1. Validate request
        if not req.user_input or not isinstance(req.user_input, str) or not req.user_input.strip():
            logger.warning("Invalid request: empty input [request_id=%s]", request_id)
            return BrainResponse(
                request_id=request_id,
                response="Please provide a valid request.",
                status=ResponseStatus.FAILURE,
                error="Empty or whitespace-only user input.",
            )

        sanitized_input = req.user_input.strip()

        # 2. Add to conversation memory if available
        if self._memory is not None:
            self._memory.add("user", sanitized_input)

        # 3. Intent Routing
        decision: RouteDecision = self._router.route(sanitized_input)
        logger.info(
            "Routing decision [request_id=%s, route=%s, target=%s, confidence=%.2f]",
            request_id,
            decision.route_type.value,
            decision.target,
            decision.confidence,
        )

        # 4. Handle Unsupported capability route
        if decision.route_type == RouteType.UNSUPPORTED:
            unsupported_msg = f"I cannot perform this action: {decision.reasoning}"
            logger.info("Controlled unsupported path taken [request_id=%s]", request_id)
            if self._memory is not None:
                self._memory.add("assistant", unsupported_msg)
            return BrainResponse(
                request_id=request_id,
                response=unsupported_msg,
                status=ResponseStatus.SUCCESS,
                error=None,
                events=[],
                metadata={
                    "route": decision.route_type.value,
                    "reasoning": decision.reasoning,
                },
            )

        # 5. Route & Execute via Agent loop
        logger.info("Executing via agent pipeline [request_id=%s]", request_id)
        try:
            run_result: RunResult = self._agent.run(sanitized_input)
        except Exception as exc:
            err_type = type(exc).__name__
            err_msg = str(exc)
            logger.error("Agent execution failed [request_id=%s, error_type=%s]: %s", request_id, err_type, err_msg)

            safe_error = f"{err_type}: {_sanitize_error(err_msg)}"
            response = BrainResponse(
                request_id=request_id,
                response=f"I encountered an error while processing your request ({err_type}: {_sanitize_error(err_msg)}).",
                status=ResponseStatus.FAILURE,
                error=safe_error,
                metadata={"route": decision.route_type.value},
            )
            if self._memory is not None:
                self._memory.add("assistant", response.response)
            return response

        # 6. Analyze execution events and determine status
        has_limit_reached = any(e.name == "__limit__" for e in run_result.events)
        has_tool_errors = any(e.error is not None for e in run_result.events)

        if has_limit_reached or (has_tool_errors and not run_result.text):
            status = ResponseStatus.PARTIAL if run_result.text else ResponseStatus.FAILURE
            error_desc = "Tool iteration limit reached" if has_limit_reached else "One or more tool executions failed"
        else:
            status = ResponseStatus.SUCCESS
            error_desc = None

        text_out = run_result.text or "(no response text)"
        logger.info(
            "Execution completed [request_id=%s, status=%s, events_count=%d]",
            request_id,
            status.value,
            len(run_result.events),
        )

        # 7. Record assistant response to memory
        if self._memory is not None:
            self._memory.add("assistant", text_out)

        return BrainResponse(
            request_id=request_id,
            response=text_out,
            status=status,
            error=error_desc,
            events=run_result.events,
            metadata={
                "events_count": len(run_result.events),
                "route": decision.route_type.value,
                "target": decision.target,
                "confidence": decision.confidence,
            },
        )


__all__ = [
    "Brain",
    "UserRequest",
    "BrainResponse",
    "ResponseStatus",
    "BrainError",
    "InvalidRequestError",
]
