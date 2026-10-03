"""Core agent: the text-in/text-out loop with tool dispatch.

UI-agnostic by design — it takes text and returns text. A terminal CLI
consumes it today; a voice layer or any other frontend can later consume
the exact same object without changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ultron.actions import PermissionDecision, PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool, ToolExecutionResult, ToolExecutor, ToolRegistry
from ultron.tools.catalog import default_catalog


@dataclass
class ToolEvent:
    """A single tool execution that happened during a run."""

    name: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    allowed: bool
    error: str | None = None


@dataclass
class RunResult:
    text: str
    events: list[ToolEvent] = field(default_factory=list)


class Agent:
    """Runs one user turn through the model, executing any tool calls it makes."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[Tool],
        audit_log: AuditLog,
        gate: PermissionGate | None = None,
        max_iterations: int = 8,
        executor: ToolExecutor | None = None,
    ) -> None:
        self._provider = provider
        self._registry = ToolRegistry(tools)
        self._tools = self._registry._tools
        self._audit = audit_log
        self._gate = gate or PermissionGate()
        self._max_iterations = max_iterations
        self._executor = executor or ToolExecutor(
            registry=self._registry,
            gate=self._gate,
            audit_log=self._audit,
        )

    @property
    def executor(self) -> ToolExecutor:
        return self._executor

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def relevant_tools(self, user_text: str, max_tools: int = 24) -> list[Tool]:
        """Tools worth showing the model for this turn.

        Sending every registered tool on every iteration bloats the prompt and
        measurably degrades tool choice on a catalog this size. Selection is by
        metadata phrase/token match, with a conservative floor:

        - tools named explicitly by a routing phrase always win;
        - everything within `max_tools` of the best token score is kept;
        - if that yields nothing, the full registry is returned rather than
          silently showing the model no tools at all.

        This only narrows what the model is *offered*. Execution still resolves
        against the full registry, so a tool the model somehow reaches for
        cannot fail merely because it was filtered out of the prompt.
        """
        catalog = default_catalog()
        allowed = {t.name for t in self._registry.all()}
        if not allowed:
            return []

        hits = catalog.match_phrases(user_text)
        chosen: list[str] = []
        for name, _phrase in hits:
            if name in allowed and name not in chosen:
                chosen.append(name)
        if chosen:
            return [t for t in self._registry.all() if t.name in set(chosen[:max_tools])]

        scored = [
            (name, score)
            for name, score, _overlap in catalog.score_tokens(user_text)
            if name in allowed
        ]
        if scored:
            best = scored[0][1]
            near = [name for name, score in scored if score >= best * 0.6]
            if near:
                keep = set(near[:max_tools])
                return [t for t in self._registry.all() if t.name in keep]

        return self._registry.all()

    def run(self, user_text: str, tools: list[Tool] | None = None) -> RunResult:
        """Run one turn.

        Args:
            user_text: The prompt for this turn.
            tools: Optional subset of specs to expose to the model. Defaults to
                every registered tool.
        """
        visible = tools if tools is not None else self._registry.all()
        specs = [t.spec for t in visible]

        result = self._provider.complete(user_text, specs)
        events: list[ToolEvent] = []
        iterations = 0

        while result.tool_calls:
            iterations += 1
            if iterations > self._max_iterations:
                self._provider.feed_tool_results(
                    [
                        ToolResult(
                            call=call,
                            output=json.dumps(
                                {"error": "tool iteration limit reached; stopping"},
                                ensure_ascii=False,
                            ),
                        )
                        for call in result.tool_calls
                    ]
                )
                events.append(
                    ToolEvent(
                        name="__limit__",
                        arguments={},
                        output={"error": "tool iteration limit reached"},
                        allowed=False,
                        error="tool iteration limit reached",
                    )
                )
                break

            tool_results: list[ToolResult] = []
            for call in result.tool_calls:
                event = self._execute(call)
                events.append(event)
                tool_results.append(
                    ToolResult(
                        call=call, output=json.dumps(event.output, ensure_ascii=False, default=str)
                    )
                )
            self._provider.feed_tool_results(tool_results)
            result = self._provider.complete(None, specs)

        return RunResult(text=result.text or "", events=events)

    def _execute(self, call: ToolCall) -> ToolEvent:
        res: ToolExecutionResult = self._executor.execute(call.name, call.arguments)
        return ToolEvent(
            name=res.tool_name,
            arguments=call.arguments,
            output=res.output,
            allowed=res.allowed,
            error=res.error,
        )

    def _record(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        output: dict[str, Any],
        decision: PermissionDecision,
    ) -> None:
        self._audit.record(tool_name, arguments, output, decision)


__all__ = ["Agent", "RunResult", "ToolEvent"]
