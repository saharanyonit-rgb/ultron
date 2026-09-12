"""Semantic memory — extends persistent memory with keyword-based retrieval.

No external dependencies. Uses TF-IDF-like scoring for relevance ranking.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ultron.memory import Memory, Turn
from ultron.memory.persistent import PersistentMemory
from ultron.models import MemoryRecord, MemoryType


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text (simple tokenization)."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "up", "about", "into", "through", "during", "before", "after",
        "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
        "neither", "each", "every", "all", "any", "few", "more", "most",
        "other", "some", "such", "no", "only", "own", "same", "than",
        "too", "very", "just", "because", "as", "until", "while",
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
        "you", "your", "yours", "yourself", "yourselves",
        "he", "him", "his", "himself", "she", "her", "hers", "herself",
        "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
        "what", "which", "who", "whom", "this", "that", "these", "those",
        "how", "when", "where", "why",
    }
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in stop_words and len(w) > 2]


def _stable_id(role: str, content: str) -> str:
    """Deterministic record ID so deletions survive restarts."""
    import hashlib

    return hashlib.sha1(f"{role}|{content}".encode("utf-8")).hexdigest()[:12]


def _compute_relevance(keywords: List[str], record_keywords: List[str]) -> float:
    """Compute relevance score between query keywords and record keywords."""
    if not keywords or not record_keywords:
        return 0.0
    common = set(keywords) & set(record_keywords)
    if not common:
        return 0.0
    return len(common) / math.sqrt(len(keywords) * len(record_keywords))


class SemanticMemory(PersistentMemory):
    """Memory with keyword-based semantic search.

    Extends PersistentMemory with:
    - Keyword extraction and indexing
    - Relevance-ranked search
    - Importance-weighted results
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__(path)
        self._records: List[MemoryRecord] = []
        self._keyword_index: Dict[str, List[int]] = {}
        self._load_records()

    def add(self, role: str, content: str) -> None:
        """Add a turn to memory and create a MemoryRecord for semantic search."""
        if not content:
            return
        super().add(role, content)
        if not any(r.content == content and r.role == role for r in self._records):
            record = MemoryRecord(
                content=content,
                role=role,
                record_id=_stable_id(role, content),
                timestamp=datetime.now(timezone.utc).isoformat(),
                keywords=_extract_keywords(content),
            )
            self._records.append(record)
            self._index_record(record)

    def add_record(self, record: MemoryRecord) -> None:
        """Add a memory record with metadata."""
        if not record.timestamp:
            record.timestamp = datetime.now(timezone.utc).isoformat()
        self._records.append(record)
        self._index_record(record)
        if record.content:
            self._turns.append(Turn(role=record.role, content=record.content))
        self._append_record_file(record)

    def _append_record_file(self, record: MemoryRecord) -> None:
        """Append a record to the JSON-lines file, including its record_id."""
        entry = {
            "ts": record.timestamp or datetime.now(timezone.utc).isoformat(),
            "role": record.role,
            "content": record.content,
            "record_id": record.record_id,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    def add_with_metadata(
        self,
        role: str,
        content: str,
        record_type: MemoryType = MemoryType.CONVERSATION,
        importance: float = 0.5,
        source: str = "",
        metadata: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
    ) -> MemoryRecord:
        """Convenience method to add a record with metadata."""
        record = MemoryRecord(
            content=content,
            role=role,
            record_type=record_type,
            importance=importance,
            source=source,
            metadata=metadata or {},
            keywords=keywords or _extract_keywords(content),
        )
        self.add_record(record)
        return record

    def search(
        self,
        query: str,
        limit: int = 10,
        min_relevance: float = 0.1,
        record_type: Optional[MemoryType] = None,
    ) -> List[MemoryRecord]:
        """Search memory by keyword relevance using inverted index lookup (O(K) candidates)."""
        query_keywords = _extract_keywords(query)
        if not query_keywords:
            return []

        # Fast lookup via inverted index to evaluate candidate record indices
        candidate_indices: set[int] = set()
        for kw in query_keywords:
            if kw in self._keyword_index:
                candidate_indices.update(self._keyword_index[kw])

        if not candidate_indices:
            return []

        scored: List[tuple[float, MemoryRecord]] = []
        for idx in candidate_indices:
            record = self._records[idx]
            if record_type and record.record_type != record_type:
                continue
            relevance = _compute_relevance(query_keywords, record.keywords)
            if relevance < min_relevance:
                continue
            score = relevance * (0.5 + record.importance)
            scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [record for _, record in scored[:limit]]

    def get_by_id(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a record by its ID."""
        for record in self._records:
            if record.record_id == record_id:
                return record
        return None

    def recent(self, limit: int = 10) -> List[MemoryRecord]:
        """Return the most recent records."""
        return list(reversed(self._records[-limit:]))

    @property
    def record_count(self) -> int:
        return len(self._records)

    def _index_record(self, record: MemoryRecord) -> None:
        """Add record keywords to the inverted index."""
        idx = len(self._records) - 1
        for keyword in record.keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            self._keyword_index[keyword].append(idx)

    def _load_records(self) -> None:
        """Load existing records from the persistent file."""
        if not self.path.is_file():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        content = entry.get("content", "")
                        role = entry.get("role", "user")
                        record = MemoryRecord(
                            content=content,
                            role=role,
                            record_id=entry.get("record_id") or _stable_id(role, content),
                            timestamp=entry.get("ts", ""),
                            keywords=_extract_keywords(content),
                        )
                        self._records.append(record)
                        self._index_record(record)
                    except Exception:
                        continue
        except OSError:
            pass

    def delete(self, record_id: str) -> bool:
        """Remove a memory record by ID (persisted to disk)."""
        for i, record in enumerate(self._records):
            if record.record_id == record_id:
                self._records.pop(i)
                self._rebuild_index()
                self._rewrite()
                return True
        return False

    def delete_matching(self, query: str, limit: int = 20) -> int:
        """Delete records matching a keyword query (forget semantics)."""
        found = self.search(query, limit=limit, min_relevance=0.02)
        removed = 0
        for record in found:
            if self.delete(record.record_id):
                removed += 1
        return removed

    def _rebuild_index(self) -> None:
        """Rebuild the inverted keyword index from scratch."""
        self._keyword_index = {}
        for idx, record in enumerate(self._records):
            for keyword in record.keywords:
                self._keyword_index.setdefault(keyword, []).append(idx)

    def _rewrite(self) -> None:
        """Rewrite the persistent file to match the current records."""
        lines = []
        for record in self._records:
            entry = {
                "ts": record.timestamp or datetime.now(timezone.utc).isoformat(),
                "role": record.role,
                "content": record.content,
                "record_id": record.record_id,
            }
            lines.append(json.dumps(entry, ensure_ascii=False, default=str))
        try:
            with self.path.open("w", encoding="utf-8") as fh:
                if lines:
                    fh.write("\n".join(lines) + "\n")
                else:
                    fh.write("")
        except OSError:
            pass


__all__ = ["SemanticMemory", "_extract_keywords", "_compute_relevance"]
