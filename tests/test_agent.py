"""Agent loop tests — uses a fake provider so no network or SDK is involved."""

from __future__ import annotations

import json
from typing import List, Optional

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.tools import ALL_TOOLS, ToolRegistry


class FakeProvider(LLMProvider):
    """Scripted provider: each `complete` call pops the next ProviderResult."""

    name = "fake"

    def __init__(self, script: List[ProviderResult]) -> None:
        self._script = list(script)
        self.calls = 0
        self.fed: List[List[ToolResult]] = []

    def complete(self, text: Optional[str], tools) -> ProviderResult:
        self.calls += 1
        if not self._script:
            return ProviderResult(text="(no more scripted steps)", tool_calls=[])
        return self._script.pop(0)

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        self.fed.append(results)


def make_agent(tmp_path, script):
    provider = FakeProvider(script)
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    return provider, Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
        max_iterations=5,
    ), audit


def test_single_response_no_tools(tmp_path):
    provider, agent, _ = make_agent(tmp_path, [ProviderResult(text="hello")])
    result = agent.run("hi")
    assert result.text == "hello"
    assert result.events == []
    assert provider.calls == 1


def test_tool_execution_and_feedback(tmp_path):
    script = [
        ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="get_system_info", arguments={})]),
        ProviderResult(text="here is your system info", tool_calls=[]),
    ]
    provider, agent, audit = make_agent(tmp_path, script)
    result = agent.run("what is my cpu?")
    assert result.text == "here is your system info"
    assert len(result.events) == 1
    event = result.events[0]
    assert event.name == "get_system_info"
    assert event.allowed is True
    assert "cpu" in event.output

    assert len(provider.fed) == 1
    assert provider.fed[0][0].call.name == "get_system_info"
    assert json.loads(provider.fed[0][0].output)["cpu"]

    entries = audit.entries()
    assert len(entries) == 1
    assert entries[0]["tool"] == "get_system_info"
    assert entries[0]["allowed"] is True


def test_unknown_tool_returns_error_not_crash(tmp_path):
    script = [
        ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="nope", arguments={})]),
        ProviderResult(text="recovered", tool_calls=[]),
    ]
    provider, agent, audit = make_agent(tmp_path, script)
    result = agent.run("do something")
    assert result.text == "recovered"
    assert result.events[0].name == "nope"
    assert "unknown tool" in result.events[0].output["error"]
    assert result.events[0].allowed is False
    assert json.loads(provider.fed[0][0].output)["error"]


def test_tool_exception_is_caught(tmp_path):
    class Boom:
        name = "boom"
        spec = object()
        mutates = True

        def run(self, **kwargs):
            raise RuntimeError("kaboom")

    provider = FakeProvider(
        [
            ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="boom", arguments={})]),
            ProviderResult(text="handled", tool_calls=[]),
        ]
    )
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(provider=provider, tools=[Boom()], audit_log=audit, gate=PermissionGate(), max_iterations=5)
    result = agent.run("go")
    assert result.text == "handled"
    assert "RuntimeError" in result.events[0].output["error"]


def test_max_iterations_guard(tmp_path):
    forever = ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="get_system_info", arguments={})])
    script = [ProviderResult(text=None, tool_calls=[ToolCall(id=str(i), name="get_system_info", arguments={})]) for i in range(100)]
    provider, agent, audit = make_agent(tmp_path, script)
    result = agent.run("loop")
    assert result.text == ""
    assert any(e.name == "__limit__" for e in result.events)
    assert provider.calls <= 6  # 1 initial + 5 iterations


def test_memory_caps_at_zero_clear(tmp_path):
    from ultron.memory import Memory

    memory = Memory()
    memory.add("user", "a")
    memory.add("assistant", "b")
    assert len(memory) == 2
    memory.clear()
    assert len(memory) == 0
