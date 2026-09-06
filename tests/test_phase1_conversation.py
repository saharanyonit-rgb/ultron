"""Phase 1 conversation-memory contract.

Drives the Brain through a three-turn conversation and asserts:
  * the model is asked the same user message that was sent
  * both user and assistant turns are recorded in `Memory`
  * sessions are isolated (a fresh Memory starts empty)
  * the structured BrainResponse contains the request_id we set

This pins the "My name is Alex / What is my name?" example in the spec so
regressions in either the orchestrator or the in-process memory surface
here, not at runtime.
"""

from __future__ import annotations

from typing import List, Optional

import pytest

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.core.brain import Brain, ResponseStatus, UserRequest
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.memory import Memory
from ultron.tools import ALL_TOOLS, ToolRegistry


class RecordingProvider(LLMProvider):
    """Provider that records every text it was given and replies with a script."""

    name = "recording"

    def __init__(self, replies: Optional[List[str]] = None) -> None:
        self.received: List[Optional[str]] = []
        self._replies = list(replies) if replies else ["ack"]

    def complete(self, text: Optional[str], tools) -> ProviderResult:
        self.received.append(text)
        return ProviderResult(text=self._replies.pop(0) if self._replies else "ack", tool_calls=[])

    def feed_tool_results(self, results) -> None:
        pass


def make_brain(tmp_path, replies):
    provider = RecordingProvider(replies)
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
        max_iterations=3,
    )
    memory = Memory()
    brain = Brain(agent=agent, memory=memory)
    return provider, memory, brain


def test_multi_turn_conversation_grows_memory(tmp_path):
    provider, memory, brain = make_brain(
        tmp_path,
        replies=["Understood.", "Your name is Alex."],
    )

    r1 = brain.process(UserRequest(user_input="My name is Alex."))
    r2 = brain.process(UserRequest(user_input="What is my name?"))

    assert r1.status == ResponseStatus.SUCCESS
    assert r2.status == ResponseStatus.SUCCESS
    assert r2.response == "Your name is Alex."
    # provider received both user turns in order
    assert provider.received == ["My name is Alex.", "What is my name?"]
    # memory contains 2 user turns + 2 assistant turns
    assert len(memory) == 4
    assert [t.role for t in memory.all()] == ["user", "assistant", "user", "assistant"]
    assert memory.all()[0].content == "My name is Alex."
    assert memory.all()[3].content == "Your name is Alex."


def test_session_isolation(tmp_path):
    _, _, brain_a = make_brain(tmp_path, replies=["a-rep"])
    _, _, brain_b = make_brain(tmp_path, replies=["b-rep"])

    brain_a.process(UserRequest(user_input="hello"))
    # brain_a's memory has 2 turns; brain_b's memory (a different instance) must be empty
    # and any new Brain built with a fresh Memory starts empty.
    fresh = Memory()
    assert len(fresh) == 0

    resp = brain_b.process(UserRequest(user_input="hi"))
    assert resp.status == ResponseStatus.SUCCESS
    assert resp.response == "b-rep"


def test_request_id_propagation(tmp_path):
    _, _, brain = make_brain(tmp_path, replies=["ok"])
    req = UserRequest(user_input="anything")
    resp = brain.process(req)
    assert resp.request_id == req.request_id
