"""Tests for persistent memory (ultron.memory.persistent)."""

from __future__ import annotations

import json
from pathlib import Path

from ultron.memory.persistent import PersistentMemory


def test_persistent_memory_loads_existing_turns(tmp_path):
    path = tmp_path / "memory.jsonl"
    # Write some turns manually
    entries = [
        {"ts": "2026-01-01T00:00:00+00:00", "role": "user", "content": "hello"},
        {"ts": "2026-01-01T00:00:01+00:00", "role": "assistant", "content": "hi there"},
    ]
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")

    mem = PersistentMemory(path)
    assert len(mem) == 2
    assert mem.all()[0].content == "hello"
    assert mem.all()[1].content == "hi there"


def test_persistent_memory_appends_to_file(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = PersistentMemory(path)

    mem.add("user", "first message")
    mem.add("assistant", "response one")

    # File should have 2 lines
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    # Verify content
    e1 = json.loads(lines[0])
    assert e1["role"] == "user"
    assert e1["content"] == "first message"
    assert "ts" in e1

    e2 = json.loads(lines[1])
    assert e2["role"] == "assistant"
    assert e2["content"] == "response one"


def test_persistent_memory_clear(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = PersistentMemory(path)
    mem.add("user", "hello")
    mem.add("assistant", "hi")
    assert len(mem) == 2

    mem.clear()
    assert len(mem) == 0
    assert path.read_text(encoding="utf-8") == ""


def test_persistent_memory_empty_file(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = PersistentMemory(path)
    assert len(mem) == 0
    assert mem.all() == []


def test_persistent_memory_nonexistent_file(tmp_path):
    path = tmp_path / "nonexistent" / "memory.jsonl"
    mem = PersistentMemory(path)
    assert len(mem) == 0
    assert path.parent.exists()


def test_persistent_memory_sessions(tmp_path):
    path = tmp_path / "memory.jsonl"
    # Write turns with a time gap to simulate two sessions
    entries = [
        {"ts": "2026-01-01T00:00:00+00:00", "role": "user", "content": "session1-hello"},
        {"ts": "2026-01-01T00:00:01+00:00", "role": "assistant", "content": "session1-response"},
        {"ts": "2026-01-01T01:00:00+00:00", "role": "user", "content": "session2-hello"},
        {"ts": "2026-01-01T01:00:01+00:00", "role": "assistant", "content": "session2-response"},
    ]
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")

    mem = PersistentMemory(path)
    sessions = mem.sessions()
    assert len(sessions) == 2
    assert sessions[0][0].content == "session1-hello"
    assert sessions[1][0].content == "session2-hello"


def test_persistent_memory_add_empty_skipped(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = PersistentMemory(path)
    mem.add("user", "")
    mem.add("assistant", "")
    assert len(mem) == 0
    assert not path.exists() or path.read_text(encoding="utf-8") == ""


def test_persistent_memory_inherits_interface(tmp_path):
    from ultron.memory import Memory
    path = tmp_path / "memory.jsonl"
    mem = PersistentMemory(path)
    assert isinstance(mem, Memory)
    mem.add("user", "test")
    assert len(mem) == 1
    assert mem.all()[0].role == "user"
