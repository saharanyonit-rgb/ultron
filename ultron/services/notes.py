"""Notes service for JARVIS — persistent note storage and retrieval."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.services.base import BaseService

logger = logging.getLogger("ultron.services.notes")


class NotesService(BaseService):
    """Manages notes with JSON file persistence."""

    _data_file = "notes.json"

    def create_note(
        self,
        title: str,
        content: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new note."""
        now = self._now_iso()
        note_id = self._generate_id()
        note = {
            "id": note_id,
            "title": str(title).strip(),
            "content": str(content).strip(),
            "tags": tags or [],
            "created_at": now,
            "updated_at": now,
            "metadata": metadata or {},
        }
        self._data["items"].append(note)
        self._persist()
        logger.info("Note created: %s", note_id)
        return note

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single note by ID."""
        for item in self._items():
            if item.get("id") == note_id:
                return item
        return None

    def list_notes(
        self,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List notes, optionally filtered by tag."""
        notes = self._items()
        if tag:
            notes = [n for n in notes if tag in n.get("tags", [])]
        notes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        return notes[:limit]

    def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an existing note."""
        for item in self._data["items"]:
            if item.get("id") == note_id:
                if title is not None:
                    item["title"] = str(title).strip()
                if content is not None:
                    item["content"] = str(content).strip()
                if tags is not None:
                    item["tags"] = tags
                if metadata is not None:
                    item["metadata"] = metadata
                item["updated_at"] = self._now_iso()
                self._persist()
                logger.info("Note updated: %s", note_id)
                return item
        return None

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        items = self._data["items"]
        for i, item in enumerate(items):
            if item.get("id") == note_id:
                self._data["items"].pop(i)
                self._persist()
                logger.info("Note deleted: %s", note_id)
                return True
        return False

    def search_notes(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search notes by title or content."""
        q = query.lower()
        notes = [
            n for n in self._items()
            if q in n.get("title", "").lower() or q in n.get("content", "").lower()
        ]
        notes.sort(key=lambda n: n.get("updated_at", ""), reverse=True)
        return notes[:limit]

    def get_all_tags(self) -> List[str]:
        """Return all unique tags across notes."""
        tags: Dict[str, bool] = {}
        for note in self._items():
            for tag in note.get("tags", []):
                tags[tag] = True
        return sorted(tags.keys())


_notes_service: Optional[NotesService] = None


def get_notes_service(data_dir: Optional[Path] = None) -> NotesService:
    global _notes_service
    if _notes_service is None:
        _notes_service = NotesService(data_dir)
    return _notes_service
