"""Memory service — backs the remember/recall/forget tools with SemanticMemory.

The service holds a reference to the SAME memory engine the Brain uses for
conversation persistence, so facts stored through the tools live in one
searchable JSONL store alongside past conversations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ultron.memory.semantic import SemanticMemory
from ultron.models import MemoryRecord, MemoryType

_memory_service: Optional["MemoryService"] = None


class MemoryService:
    """Thin wrapper exposing keep/recall semantics on top of SemanticMemory."""

    def __init__(self, engine: Optional[SemanticMemory] = None) -> None:
        self._engine = engine

    @property
    def engine(self) -> Optional[SemanticMemory]:
        return self._engine

    def set_engine(self, engine: Optional[SemanticMemory]) -> None:
        """Attach the runtime memory engine (called at startup)."""
        self._engine = engine

    @property
    def configured(self) -> bool:
        return self._engine is not None

    def remember(self, fact: str, topic: str = "") -> Dict[str, Any]:
        """Store a fact/preference so it can be recalled later."""
        engine = self._require_engine()
        content = f"[{topic.strip()}] {fact.strip()}" if topic and topic.strip() else fact.strip()
        record = engine.add_with_metadata(
            role="assistant",
            content=content,
            record_type=MemoryType.FACT,
            importance=0.9,
            metadata={"topic": topic.strip()} if topic and topic.strip() else {},
        )
        return {
            "remembered": True,
            "record_id": record.record_id,
            "fact": fact.strip(),
            "topic": topic.strip() if topic and topic.strip() else "",
        }

    def recall(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memory for records relevant to `query`."""
        engine = self._require_engine()
        records = engine.search(query, limit=limit, min_relevance=0.05)
        return [self._record_to_dict(r) for r in records]

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent memory records."""
        engine = self._require_engine()
        return [self._record_to_dict(r) for r in engine.recent(limit=limit)]

    def forget(self, query: str = "", record_id: str = "") -> Dict[str, Any]:
        """Delete memories by ID or by keyword query."""
        engine = self._require_engine()
        removed = 0
        if record_id:
            engine.delete(record_id)
            removed = 1
        elif query:
            removed = engine.delete_matching(query, limit=20)
        return {"forgotten": removed > 0, "removed": removed}

    @staticmethod
    def _record_to_dict(record: MemoryRecord) -> Dict[str, Any]:
        return {
            "record_id": record.record_id,
            "role": record.role,
            "content": record.content,
            "type": getattr(record.record_type, "value", str(record.record_type)) if record.record_type else "unknown",
        }

    def _require_engine(self) -> SemanticMemory:
        if self._engine is None:
            raise RuntimeError("Memory is not configured. Start JARVIS to enable persistent memory.")
        return self._engine


def get_memory_service() -> MemoryService:
    """Return the process-wide memory service singleton."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


__all__ = ["MemoryService", "get_memory_service"]