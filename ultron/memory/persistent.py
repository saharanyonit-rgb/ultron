"""Persistent conversation memory — extends in-process Memory with file storage.

Turns are appended to a JSON-lines file on every add().  On construction,
existing turns are loaded so conversation history survives restarts.

The in-memory `Memory` class from Phase 1 is the base; PersistentMemory
adds disk persistence without changing the public interface.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.memory import Memory, Turn


class PersistentMemory(Memory):
    """Memory that persists turns to a JSON-lines file.

    Inherits all Phase 1 Memory behavior.  Adds:
    - load from file on construction
    - append to file on each add()
    - clear also truncates the file
    """

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def add(self, role: str, content: str) -> None:
        """Add a turn to memory and persist it to disk."""
        super().add(role, content)
        if content:
            self._append(role, content)

    def clear(self) -> None:
        """Clear in-memory turns and truncate the file."""
        super().clear()
        try:
            self._path.write_text("", encoding="utf-8")
        except OSError:
            pass

    def sessions(self) -> List[List[Turn]]:
        """Return turns grouped by session (separated by blank lines in file).

        Each session is a list of Turns.  A new session starts when a
        consecutive pair of user turns has a gap (indicating a restart).
        """
        if not self._path.is_file():
            return []
        sessions: List[List[Turn]] = []
        current: List[Turn] = []
        prev_ts: Optional[str] = None
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("ts", "")
                    turn = Turn(role=entry.get("role", ""), content=entry.get("content", ""))
                    # Heuristic: if timestamp gap > 5 minutes, start new session
                    if prev_ts and ts and self._gap_exceeded(prev_ts, ts, seconds=300):
                        if current:
                            sessions.append(current)
                        current = []
                    current.append(turn)
                    prev_ts = ts
        except OSError:
            pass
        if current:
            sessions.append(current)
        return sessions

    def _load(self) -> None:
        """Load existing turns from the file into memory."""
        if not self._path.is_file():
            return
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Bypass the super().add() to avoid re-writing to file
                    self._turns.append(
                        Turn(
                            role=entry.get("role", ""),
                            content=entry.get("content", ""),
                        )
                    )
        except OSError:
            pass

    def _append(self, role: str, content: str) -> None:
        """Append a single turn to the file."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        try:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass

    @staticmethod
    def _gap_exceeded(ts1: str, ts2: str, seconds: int = 300) -> bool:
        """Check if the gap between two ISO timestamps exceeds `seconds`."""
        try:
            d1 = datetime.fromisoformat(ts1)
            d2 = datetime.fromisoformat(ts2)
            return abs((d2 - d1).total_seconds()) > seconds
        except (ValueError, TypeError):
            return False


__all__ = ["PersistentMemory"]
