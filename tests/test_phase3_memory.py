"""Tests for semantic memory (ultron.memory.semantic)."""
from __future__ import annotations
import json
from pathlib import Path
from ultron.memory.semantic import SemanticMemory, _extract_keywords, _compute_relevance
from ultron.models import MemoryRecord, MemoryType
def test_add_record_with_keywords(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    record = MemoryRecord(
        content="Python is a programming language",
        role="user",
        keywords=["python", "programming", "language"],
    )
    mem.add_record(record)
    assert mem.record_count == 1
    assert len(mem) == 1
def test_search_by_relevance(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    mem.add_with_metadata("user", "Python programming tutorial", MemoryType.FACT, 0.8)
    mem.add_with_metadata("user", "JavaScript web development", MemoryType.FACT, 0.6)
    mem.add_with_metadata("user", "Machine learning with Python", MemoryType.FACT, 0.9)
    results = mem.search("Python programming")
    assert len(results) >= 2
    assert any("Python" in r.content for r in results)
def test_search_with_type_filter(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    mem.add_with_metadata("user", "Python programming", MemoryType.FACT)
    mem.add_with_metadata("user", "Task completed", MemoryType.TASK)
    results = mem.search("programming", record_type=MemoryType.FACT)
    assert len(results) == 1
    assert results[0].record_type == MemoryType.FACT
def test_search_min_relevance(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    mem.add_with_metadata("user", "Python programming tutorial", MemoryType.FACT)
    results = mem.search("Python", min_relevance=0.9)
    assert len(results) == 0
def test_get_by_id(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    record = mem.add_with_metadata("user", "test content", MemoryType.NOTE)
    found = mem.get_by_id(record.record_id)
    assert found is not None
    assert found.content == "test content"
def test_recent_records(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    for i in range(5):
        mem.add_with_metadata("user", f"message {i}", MemoryType.CONVERSATION)
    recent = mem.recent(3)
    assert len(recent) == 3
    assert recent[0].content == "message 4"
def test_keyword_extraction():
    keywords = _extract_keywords("Python is a great programming language")
    assert "python" in keywords
    assert "programming" in keywords
    assert "language" in keywords
    assert "is" not in keywords
    assert "a" not in keywords
def test_relevance_scoring():
    score = _compute_relevance(["python", "code"], ["python", "code", "test"])
    assert score > 0
    assert score <= 1.0
def test_record_count(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    assert mem.record_count == 0
    mem.add_with_metadata("user", "first", MemoryType.CONVERSATION)
    assert mem.record_count == 1
    mem.add_with_metadata("user", "second", MemoryType.CONVERSATION)
    assert mem.record_count == 2
def test_search_empty_query(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    mem.add_with_metadata("user", "test content", MemoryType.CONVERSATION)
    results = mem.search("")
    assert len(results) == 0
def test_search_no_matches(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    mem.add_with_metadata("user", "Python programming", MemoryType.CONVERSATION)
    results = mem.search("quantum physics", min_relevance=0.1)
    assert len(results) == 0
def test_inherits_persistent_memory(tmp_path):
    from ultron.memory import Memory
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    assert isinstance(mem, Memory)
    mem.add("user", "test")
    assert len(mem) == 1
def test_inverted_index_search_efficiency(tmp_path):
    path = tmp_path / "memory.jsonl"
    mem = SemanticMemory(path)
    # Populate memory with 100 records
    for i in range(100):
        mem.add_with_metadata("user", f"Topic item number {i} data record", MemoryType.CONVERSATION)
    # Add a specific target record
    target = mem.add_with_metadata("user", "Specialized unique keyword zenith", MemoryType.FACT)
    # Ensure inverted index indexed the keyword
    assert "zenith" in mem._keyword_index
    assert len(mem._keyword_index["zenith"]) == 1
    # Search for unique keyword
    results = mem.search("zenith")
    assert len(results) == 1
    assert results[0].record_id == target.record_id
