"""Unit tests for the JARVIS Core Brain / Orchestrator (`ultron.core.brain`)."""

from __future__ import annotations

import json
from typing import List, Optional

import pytest

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.core.brain import (
    Brain,
    BrainResponse,
    ResponseStatus,
    UserRequest,
)
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.memory import Memory
from ultron.tools import ALL_TOOLS, ToolRegistry


class ScriptedProvider(LLMProvider):
    name = "scripted_brain_provider"

    def __init__(self, script: Optional[List[ProviderResult]] = None) -> None:
        self._script = list(script) if script else []
        self.should_fail = False

    def complete(self, text: Optional[str], tools) -> ProviderResult:
        if self.should_fail:
            raise RuntimeError("LLM Provider Connection Failed")
        if not self._script:
            return ProviderResult(text="default scripted response", tool_calls=[])
        return self._script.pop(0)

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        pass


def make_brain(tmp_path, script=None):
    provider = ScriptedProvider(script)
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
        max_iterations=5,
    )
    memory = Memory()
    brain = Brain(agent=agent, memory=memory)
    return provider, agent, memory, brain


# --- Test 1 — Valid request ---
def test_valid_request(tmp_path):
    provider, agent, memory, brain = make_brain(
        tmp_path, [ProviderResult(text="Hello from Brain", tool_calls=[])]
    )
    request = UserRequest(user_input="Hello Ultron")
    response: BrainResponse = brain.process(request)

    assert response.status == ResponseStatus.SUCCESS
    assert response.response == "Hello from Brain"
    assert response.request_id == request.request_id
    assert response.error is None
    assert len(memory) == 2  # user turn + assistant turn


# --- Test 2 — Invalid request ---
def test_invalid_request(tmp_path):
    _, _, memory, brain = make_brain(tmp_path)
    for bad_input in ("", "   ", None):
        request = UserRequest(user_input=bad_input)
        response = brain.process(request)
        assert response.status == ResponseStatus.FAILURE
        assert "valid request" in response.response.lower()
        assert response.error is not None
    assert len(memory) == 0  # Invalid input should not pollute memory


# --- Test 3 — LLM failure ---
def test_llm_failure(tmp_path):
    provider, _, memory, brain = make_brain(tmp_path)
    provider.should_fail = True
    request = UserRequest(user_input="What is the weather?")
    response = brain.process(request)

    assert response.status == ResponseStatus.FAILURE
    assert "error" in response.response.lower()
    assert "RuntimeError" in response.error
    assert len(memory) == 2  # Turn recorded in memory with error notice


# --- Test 4 — Agent failure ---
def test_agent_failure_handled(tmp_path):
    class FailingAgent(Agent):
        def run(self, user_text: str):
            raise ValueError("Agent internal pipeline crash")

    provider = ScriptedProvider()
    audit = AuditLog(tmp_path / "audit.log")
    failing_agent = FailingAgent(
        provider=provider, tools=[], audit_log=audit, gate=PermissionGate()
    )
    brain = Brain(agent=failing_agent)

    response = brain.process("test run")
    assert response.status == ResponseStatus.FAILURE
    assert "ValueError" in response.error
    assert "error" in response.response.lower()


# --- Test 5 — Tool failure ---
def test_tool_failure_propagation(tmp_path):
    # Model requests unknown tool 'broken_tool'
    script = [
        ProviderResult(
            text=None,
            tool_calls=[ToolCall(id="c1", name="broken_tool", arguments={})],
        ),
        ProviderResult(text="Recovered after tool error", tool_calls=[]),
    ]
    _, _, _, brain = make_brain(tmp_path, script)
    response = brain.process("Run broken tool")

    assert response.status == ResponseStatus.SUCCESS
    assert response.response == "Recovered after tool error"
    assert len(response.events) == 1
    assert response.events[0].name == "broken_tool"
    assert response.events[0].allowed is False


# --- Test 6 — Unexpected exception ---
def test_unexpected_exception_safety(tmp_path):
    class ExplodingAgent(Agent):
        def run(self, user_text: str):
            raise TypeError("Secret internal crash (API_KEY=SECRET_12345)")

    provider = ScriptedProvider()
    audit = AuditLog(tmp_path / "audit.log")
    exploding_agent = ExplodingAgent(
        provider=provider, tools=[], audit_log=audit, gate=PermissionGate()
    )
    brain = Brain(agent=exploding_agent)

    response = brain.process("explode")
    assert response.status == ResponseStatus.FAILURE
    # Ensure raw sensitive string is not present in user-facing response text
    assert "SECRET_12345" not in response.response


# --- Test 7 — Request isolation ---
def test_request_isolation(tmp_path):
    _, _, memory, brain = make_brain(
        tmp_path,
        [
            ProviderResult(text="Ans 1"),
            ProviderResult(text="Ans 2"),
        ],
    )
    req1 = UserRequest(user_input="Req 1")
    req2 = UserRequest(user_input="Req 2")

    resp1 = brain.process(req1)
    resp2 = brain.process(req2)

    assert resp1.request_id != resp2.request_id
    assert resp1.request_id == req1.request_id
    assert resp2.request_id == req2.request_id
    assert resp1.response == "Ans 1"
    assert resp2.response == "Ans 2"
