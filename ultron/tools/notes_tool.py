"""Notes tool — create, read, update, and search personal notes."""

from __future__ import annotations

from typing import Any, Dict

from ultron.services import get_notes_service
from ultron.tools.base import Tool


class CreateNoteTool(Tool):
    """Create a new note."""

    name = "create_note"
    description = (
        "Create a new note. Use when the user asks to create a note, write something down, "
        "save a note, or add an idea. Returns the created note with its ID."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the note.",
            },
            "content": {
                "type": "string",
                "description": "Optional content or body of the note.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tags for the note.",
            },
        },
        "required": ["title"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "created_at": {"type": "string"},
            "error": {"type": "string"},
        },
    }

    def run(self, title: str, content: str = "", tags: list[str] | None = None, **_: Any) -> Dict[str, Any]:
        try:
            service = get_notes_service()
            note = service.create_note(title=title, content=content, tags=tags or [])
            return {"created": True, "note": note}
        except Exception as exc:
            return {"error": f"Failed to create note: {exc}"}


class ListNotesTool(Tool):
    """List all notes, optionally filtered by tag."""

    name = "list_notes"
    description = (
        "List all notes, optionally filtered by tag. "
        "Use when the user asks to show notes, list notes, or see their notes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Optional tag to filter notes by.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of notes to return (default: 20).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "notes": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, tag: str | None = None, limit: int = 20, **_: Any) -> Dict[str, Any]:
        try:
            service = get_notes_service()
            notes = service.list_notes(tag=tag, limit=limit)
            return {"notes": notes, "count": len(notes)}
        except Exception as exc:
            return {"error": f"Failed to list notes: {exc}", "notes": [], "count": 0}


class SearchNotesTool(Tool):
    """Search notes by title or content."""

    name = "search_notes"
    description = (
        "Search notes by keyword in title or content. "
        "Use when the user asks to search notes, find notes about something, "
        "or look for a specific note."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword to search for in note titles and content.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 10).",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "notes": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, query: str, limit: int = 10, **_: Any) -> Dict[str, Any]:
        try:
            service = get_notes_service()
            notes = service.search_notes(query=query, limit=limit)
            return {"notes": notes, "count": len(notes)}
        except Exception as exc:
            return {"error": f"Failed to search notes: {exc}", "notes": [], "count": 0}
