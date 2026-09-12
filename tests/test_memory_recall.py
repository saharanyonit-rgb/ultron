"""Tests for long-term memory: semantic delete, memory service, tools, and Brain recall."""

from __future__ import annotations

import pytest

from ultron.core.brain import Brain
from ultron.memory.semantic import SemanticMemory
from ultron.models import MemoryType
from ultron.services import get_memory_service
from ultron.services import memory as memory_service_mod
from ultron.tools import ALL_TOOLS, ToolRegistry


@pytest.fixture(autouse=True)
def _reset_memory_service():
    """Isolate the process-wide memory service singleton between tests."""
    old = memory_service_mod._memory_service
    memory_service_mod._memory_service = None
    yield
    memory_service_mod._memory_service = old


def _configured(tmp_path):
    engine = SemanticMemory(tmp_path / "memory.jsonl")
    get_memory_service().set_engine(engine)
    return engine


# ── SemanticMemory persistence / deletion ─────────────────────────

class TestSemanticMemoryDelete:
    def test_delete_removes_record_and_persists(self, tmp_path):
        mem = SemanticMemory(tmp_path / "memory.jsonl")
        mem.add_with_metadata("assistant", "Boss likes dark mode", record_type=MemoryType.FACT, importance=0.9)
        recs = mem.search("dark mode", min_relevance=0.0)
        assert len(recs) == 1
        rid = recs[0].record_id

        assert mem.delete(rid) is True
        assert mem.search("dark mode", min_relevance=0.0) == []

        # Survives reload
        mem2 = SemanticMemory(tmp_path / "memory.jsonl")
        assert mem2.search("dark mode", min_relevance=0.0) == []

    def test_delete_matching_removes_by_query(self, tmp_path):
        mem = SemanticMemory(tmp_path / "memory.jsonl")
        mem.add_with_metadata("assistant", "my name is alex", record_type=MemoryType.FACT, importance=0.9)
        mem.add_with_metadata("assistant", "the sky is blue", record_type=MemoryType.FACT, importance=0.9)
        removed = mem.delete_matching("alex")
        assert removed == 1
        assert mem.search("alex", min_relevance=0.0) == []

    def test_stable_record_ids_across_reload(self, tmp_path):
        mem = SemanticMemory(tmp_path / "memory.jsonl")
        mem.add_with_metadata("assistant", "pepper is a dog", record_type=MemoryType.FACT, importance=0.9)
        rec1 = mem.search("pepper", min_relevance=0.0)[0]

        mem2 = SemanticMemory(tmp_path / "memory.jsonl")
        rec2 = mem2.search("pepper", min_relevance=0.0)[0]
        assert rec1.record_id == rec2.record_id


# ── MemoryService ──────────────────────────────────────────────

class TestMemoryService:
    def test_remember_and_recall(self, tmp_path):
        svc = get_memory_service()
        engine = SemanticMemory(tmp_path / "memory.jsonl")
        svc.set_engine(engine)

        svc.remember("my name is alex", topic="personal")
        results = svc.recall("what's my name")
        assert len(results) >= 1
        assert "alex" in results[0]["content"]

    def test_recent_and_forget(self, tmp_path):
        svc = get_memory_service()
        svc.set_engine(SemanticMemory(tmp_path / "memory.jsonl"))
        svc.remember("prefer python over javascript")
        svc.remember("birthday is may 12")

        assert len(svc.recent(limit=10)) == 2
        result = svc.forget(query="python")
        assert result["removed"] == 1
        assert len(svc.recent(limit=10)) == 1

    def test_unconfigured_raises(self):
        svc = get_memory_service()
        with pytest.raises(RuntimeError):
            svc.remember("x")


# ── Memory tools ───────────────────────────────────────────────

class TestMemoryTools:
    def test_memory_tools_registered(self):
        registry = ToolRegistry(ALL_TOOLS)
        for name in ("remember", "recall", "list_memories", "forget"):
            assert registry.exists(name), f"{name} should be registered"

    def test_remember_tool_stores_and_recall_finds(self, tmp_path):
        _configured(tmp_path)
        registry = ToolRegistry(ALL_TOOLS)

        out = registry.get("remember").run(fact="my favorite color is green", topic="preferences")
        assert out["remembered"] is True

        res = registry.get("recall").run(query="favorite color")
        assert res["count"] >= 1
        assert "green" in res["results"][0]["content"]

    def test_list_and_forget_tools(self, tmp_path):
        _configured(tmp_path)
        registry = ToolRegistry(ALL_TOOLS)
        registry.get("remember").run(fact="I hate mornings", topic="preferences")

        listed = registry.get("list_memories").run(limit=10)
        assert listed["count"] >= 1

        gone = registry.get("forget").run(query="mornings")
        assert gone["forgotten"] is True

        gone_again = registry.get("forget").run(query="mornings")
        assert gone_again["removed"] == 0

    def test_tools_error_gracefully_when_unconfigured(self):
        registry = ToolRegistry(ALL_TOOLS)
        out = registry.get("remember").run(fact="something")
        assert out["remembered"] is False
        assert "not configured" in out["error"]


# ── Brain recall context ───────────────────────────────────────

class _RecordingProvider:
    name = "recording"

    def __init__(self, replies=("ack",)):
        self.received = []
        self._replies = list(replies)

    def complete(self, text, tools):
        self.received.append(text)
        return type("R", (), {"text": self._replies.pop(0) if self._replies else "ack", "tool_calls": []})()

    def feed_tool_results(self, results):
        pass


def _make_brain(memory):
    provider = _RecordingProvider(replies=["ok", "ok"])
    from ultron.actions import PermissionGate
    from ultron.actions.audit_log import AuditLog
    from ultron.core.agent import Agent
    from ultron.tools import ALL_TOOLS, ToolRegistry
    import tempfile

    audit_dir = tempfile.mkdtemp()
    agent = Agent(
        provider=provider,
        tools=ToolRegistry(ALL_TOOLS).all(),
        audit_log=AuditLog(f"{audit_dir}/audit.log"),
        gate=PermissionGate(),
        max_iterations=3,
    )
    return provider, Brain(agent=agent, memory=memory)


def test_brain_injects_recent_turns(tmp_path):
    mem = SemanticMemory(tmp_path / "mem.jsonl")
    provider, brain = _make_brain(mem)

    provider._replies = ["Understood.", "Your name is Alex."]
    brain.process("My name is Alex.")
    brain.process("What is my name?")

    assert provider.received[1].endswith("What is my name?")
    assert "Recent conversation:" in provider.received[1]
    assert "My name is Alex." in provider.received[1]


def test_brain_recalls_earlier_session(tmp_path):
    """A fact stored 'yesterday' (in a prior file) is recalled today."""
    import json
    from datetime import datetime, timezone

    path = tmp_path / "mem.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": "assistant",
            "content": "[preferences] I prefer coffee",
            "record_id": "abc123def456",
        }) + "\n")

    mem = SemanticMemory(path)
    provider, brain = _make_brain(mem)
    brain.process("What do I prefer to drink?")
    assert "coffee" in provider.received[0]
    assert "Earlier remembered:" in provider.received[0]


def test_brain_no_memory_no_preamble(tmp_path):
    from ultron.memory import Memory

    provider, brain = _make_brain(Memory())
    brain.process("hi")
    assert provider.received[0] == "hi"