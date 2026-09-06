"""Shared base for JARVIS service persistence layers."""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.services")


class BaseService(ABC):
    """Base class for JSON-file-backed service persistence."""

    _data_file: str = ""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        if data_dir is None:
            data_dir = Path.home() / ".jarvis"
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._data_dir / self._data_file
        self._lock_file = self._data_dir / (self._data_file + ".lock")
        self._data: Dict[str, Any] = {"items": [], "updated_at": None}
        self._load()

    def _load(self) -> None:
        if not self._file_path.is_file():
            return
        try:
            with self._file_path.open("r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load %s: %s", self._data_file, exc)
            self._data = {"items": [], "updated_at": None}

    def _persist(self) -> None:
        self._data["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            with self._file_path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to persist %s: %s", self._data_file, exc)

    def _generate_id(self) -> str:
        return str(uuid.uuid4())[:12]

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _items(self) -> List[Dict[str, Any]]:
        return self._data.get("items", [])
