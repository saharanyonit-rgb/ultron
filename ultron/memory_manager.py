"""Memory Manager for JARVIS Phase 5.

Provides a layered memory system that persists knowledge across sessions.

Memory types:
- Working Memory: bounded buffer for current goal context
- Episodic Memory: past goal executions
- Semantic Memory: facts and knowledge (extends existing)
- Project Memory: per-project context
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.memory_manager")


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROJECT = "project"


@dataclass
class MemoryEntry:
    """A single memory record."""
    content: str
    memory_type: str = MemoryType.WORKING.value
    importance: float = 0.5
    source: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    entry_id: str = ""

    def __post_init__(self):
        if not self.entry_id:
            import hashlib
            self.entry_id = hashlib.md5(
                f"{self.content}:{self.timestamp}".encode()
            ).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "source": self.source,
            "tags": self.tags,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EpisodeRecord:
    """Record of a completed goal execution."""
    goal_id: str = ""
    goal_description: str = ""
    outcome: str = ""
    tasks_completed: int = 0
    tasks_failed: int = 0
    duration_seconds: float = 0.0
    strategies_used: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "outcome": self.outcome,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "duration_seconds": self.duration_seconds,
            "strategies_used": self.strategies_used,
            "lessons_learned": self.lessons_learned,
            "tools_used": self.tools_used,
            "timestamp": self.timestamp,
        }


class MemoryManager:
    """Layered memory system for autonomous execution.

    Provides:
    - Working memory: bounded buffer for current context
    - Episodic memory: past goal executions
    - Semantic memory: keyword-based search
    - Project memory: per-project context
    """

    def __init__(
        self,
        working_memory_limit: int = 50,
        episodic_memory_limit: int = 200,
        persistence_path: Optional[str | Path] = None,
    ) -> None:
        self._working_limit = working_memory_limit
        self._episodic_limit = episodic_memory_limit
        self._persistence_path = Path(persistence_path) if persistence_path else None

        self._working: List[MemoryEntry] = []
        self._episodic: List[EpisodeRecord] = []
        self._semantic: List[MemoryEntry] = []
        self._project: Dict[str, List[MemoryEntry]] = {}

        if self._persistence_path:
            self._load()

    # ── Working Memory ──────────────────────────────────────────────

    def add_working(self, content: str, **kwargs: Any) -> MemoryEntry:
        """Add to working memory (bounded)."""
        entry = MemoryEntry(
            content=content,
            memory_type=MemoryType.WORKING.value,
            **kwargs,
        )
        self._working.append(entry)
        if len(self._working) > self._working_limit:
            self._working = self._working[-self._working_limit:]
        return entry

    def get_working(self, limit: int = 10) -> List[MemoryEntry]:
        return list(self._working[-limit:])

    def clear_working(self) -> None:
        self._working.clear()

    # ── Episodic Memory ─────────────────────────────────────────────

    def store_episode(self, episode: EpisodeRecord) -> None:
        """Store a completed goal execution episode."""
        self._episodic.append(episode)
        if len(self._episodic) > self._episodic_limit:
            self._episodic = self._episodic[-self._episodic_limit:]
        self._persist()

    def get_episodes(
        self,
        outcome: Optional[str] = None,
        limit: int = 10,
    ) -> List[EpisodeRecord]:
        """Retrieve episodes, optionally filtered by outcome."""
        episodes = self._episodic
        if outcome:
            episodes = [e for e in episodes if e.outcome == outcome]
        return list(episodes[-limit:])

    def search_episodes(self, query: str, limit: int = 5) -> List[EpisodeRecord]:
        """Search episodes by keyword relevance."""
        query_words = set(query.lower().split())
        scored = []
        for ep in self._episodic:
            text = f"{ep.goal_description} {' '.join(ep.strategies_used)} {' '.join(ep.lessons_learned)}".lower()
            ep_words = set(text.split())
            overlap = len(query_words & ep_words)
            if overlap > 0:
                scored.append((overlap, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    # ── Semantic Memory ─────────────────────────────────────────────

    def add_semantic(self, content: str, **kwargs: Any) -> MemoryEntry:
        """Add a fact or knowledge entry."""
        entry = MemoryEntry(
            content=content,
            memory_type=MemoryType.SEMANTIC.value,
            **kwargs,
        )
        self._semantic.append(entry)
        self._persist()
        return entry

    def search_semantic(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search semantic memory by keyword relevance."""
        query_words = set(query.lower().split())
        scored = []
        for entry in self._semantic:
            entry_words = set(entry.content.lower().split())
            overlap = len(query_words & entry_words)
            if overlap > 0:
                score = overlap * entry.importance
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    # ── Project Memory ──────────────────────────────────────────────

    def add_project(self, project: str, content: str, **kwargs: Any) -> MemoryEntry:
        """Add memory for a specific project."""
        entry = MemoryEntry(
            content=content,
            memory_type=MemoryType.PROJECT.value,
            **kwargs,
        )
        if project not in self._project:
            self._project[project] = []
        self._project[project].append(entry)
        self._persist()
        return entry

    def get_project(self, project: str, limit: int = 20) -> List[MemoryEntry]:
        """Get memory entries for a project."""
        return list(self._project.get(project, [])[-limit:])

    # ── Context Building ────────────────────────────────────────────

    def build_context_for_goal(
        self,
        goal_description: str,
        include_working: bool = True,
        include_episodes: bool = True,
        include_semantic: bool = True,
        max_tokens: int = 2000,
    ) -> str:
        """Build a context string from relevant memories."""
        parts = []

        if include_working:
            working = self.get_working(limit=5)
            if working:
                parts.append("Current context:")
                for entry in working:
                    parts.append(f"  - {entry.content[:200]}")

        if include_episodes:
            episodes = self.search_episodes(goal_description, limit=3)
            if episodes:
                parts.append("Relevant past experiences:")
                for ep in episodes:
                    parts.append(f"  - [{ep.outcome}] {ep.goal_description[:100]}")

        if include_semantic:
            semantic = self.search_semantic(goal_description, limit=5)
            if semantic:
                parts.append("Relevant knowledge:")
                for entry in semantic:
                    parts.append(f"  - {entry.content[:200]}")

        context = "\n".join(parts)
        if len(context) > max_tokens:
            context = context[:max_tokens]
        return context

    # ── Serialization ───────────────────────────────────────────────

    def _persist(self) -> None:
        """Persist memory to disk."""
        if not self._persistence_path:
            return

        data = {
            "episodic": [e.to_dict() for e in self._episodic],
            "semantic": [e.to_dict() for e in self._semantic],
            "project": {
                k: [e.to_dict() for e in v]
                for k, v in self._project.items()
            },
        }

        self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._persistence_path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("Failed to persist memory: %s", exc)

    def _load(self) -> None:
        """Load memory from disk."""
        if not self._persistence_path or not self._persistence_path.is_file():
            return

        try:
            with self._persistence_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                for e in data.get("episodic", []):
                    self._episodic.append(EpisodeRecord(**{
                        k: v for k, v in e.items()
                        if k in EpisodeRecord.__dataclass_fields__
                    }))
                for e in data.get("semantic", []):
                    self._semantic.append(MemoryEntry.from_dict(e))
                for project, entries in data.get("project", {}).items():
                    self._project[project] = [MemoryEntry.from_dict(e) for e in entries]
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load memory: %s", exc)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "working": len(self._working),
            "episodic": len(self._episodic),
            "semantic": len(self._semantic),
            "projects": len(self._project),
            "total": len(self._working) + len(self._episodic) + len(self._semantic),
        }


__all__ = [
    "MemoryType",
    "MemoryEntry",
    "EpisodeRecord",
    "MemoryManager",
]
