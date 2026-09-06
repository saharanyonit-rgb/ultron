"""Core agent: the text-in/text-out loop with tool dispatch.

UI-agnostic by design — it takes text and returns text. A terminal CLI
consumes it today; a voice layer or any other frontend can later consume
the exact same object without changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.actions import PermissionDecision, PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.tools import Tool, ToolExecutionResult, ToolExecutor, ToolRegistry


@dataclass
class ToolEvent:
    """A single tool execution that happened during a run."""

    name: str
    arguments: Dict[str, Any]
    output: Dict[str, Any]
    allowed: bool
    error: Optional[str] = None


@dataclass
class RunResult:
    text: str
    events: List[ToolEvent] = field(default_factory=list)


class Agent:
    """Runs one user turn through the model, executing any tool calls it makes."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        audit_log: AuditLog,
        gate: Optional[PermissionGate] = None,
        max_iterations: int = 8,
        executor: Optional[ToolExecutor] = None,
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

    def run(self, user_text: str) -> RunResult:
        result = self._provider.complete(user_text, [t.spec for t in self._registry.all()])
        events: List[ToolEvent] = []
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

            tool_results: List[ToolResult] = []
            for call in result.tool_calls:
                event = self._execute(call)
                events.append(event)
                tool_results.append(
                    ToolResult(call=call, output=json.dumps(event.output, ensure_ascii=False, default=str))
                )
            self._provider.feed_tool_results(tool_results)
            result = self._provider.complete(None, [t.spec for t in self._registry.all()])

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
        arguments: Dict[str, Any],
        output: Dict[str, Any],
        decision: PermissionDecision,
    ) -> None:
        self._audit.record(tool_name, arguments, output, decision)


__all__ = ["Agent", "RunResult", "ToolEvent"]
