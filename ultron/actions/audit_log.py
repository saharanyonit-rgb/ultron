"""Append-only audit log for every action the assistant takes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ultron.actions import PermissionDecision


class AuditLog:
    """JSON-lines log of tool executions, flushed on every record.

    Path is configurable (ULTRON_AUDIT_LOG) so tests can point it anywhere.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
        decision: PermissionDecision,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "allowed": decision.allowed,
            "reason": decision.reason,
        }
        line = json.dumps(entry, ensure_ascii=False, default=str)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def entries(self) -> list[Dict[str, Any]]:
        if not self._path.is_file():
            return []
        out: list[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if raw:
                    try:
                        out.append(json.loads(raw))
                    except json.JSONDecodeError:
                        continue
        return out


__all__ = ["AuditLog"]
