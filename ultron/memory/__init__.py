"""In-process conversation memory — one session, no persistence.

This is deliberately minimal: it holds the current conversation so the CLI
can display history and a future voice layer can render the same turns. No
database, no disk. Long-term memory is a later architecture round.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str


class Memory:
    """A plain in-process list of user/assistant turns."""

    def __init__(self) -> None:
        self._turns: List[Turn] = []

    def add(self, role: str, content: str) -> None:
        if not content:
            return
        self._turns.append(Turn(role=role, content=content))

    def all(self) -> List[Turn]:
        return list(self._turns)

    def clear(self) -> None:
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)


__all__ = ["Memory", "Turn"]
