"""Long-term memory tools — remember, recall, list, and forget facts.

These give JARVIS a persistent personal memory: the user can say
"remember that my name is Alex" and later ask "what do you know about me?".
Backed by the MemoryService / SemanticMemory engine.
"""

from __future__ import annotations

from typing import Any, Dict

from ultron.services import get_memory_service
from ultron.tools.base import Tool


class RememberTool(Tool):
    """Store a fact or preference for long-term recall."""

    name = "remember"
    description = (
        "Store a fact, preference, or personal detail about the user for long-term memory. "
        "Use whenever the user says things like 'remember that ...', 'my name is ...', "
        "'call me ...', 'I prefer ...', or wants JARVIS to know something in the future. "
        "The fact is persisted across restarts and injected into future conversations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "fact": {
                "type": "string",
                "description": "The fact or preference to remember.",
            },
            "topic": {
                "type": "string",
                "description": "Optional topic/grouping, e.g. 'preferences', 'personal', 'work'.",
            },
        },
        "required": ["fact"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "remembered": {"type": "boolean"},
            "record_id": {"type": "string"},
            "fact": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, fact: str, topic: str = "", **_: Any) -> Dict[str, Any]:
        try:
            return get_memory_service().remember(fact, topic)
        except Exception as exc:
            return {"remembered": False, "error": f"Failed to remember: {exc}"}


class RecallTool(Tool):
    """Search long-term and past-conversation memory."""

    name = "recall"
    description = (
        "Search JARVIS long-term memory and past conversations for relevant facts. "
        "Use when the user asks 'what do you know about me?', 'do you remember ...', "
        "'what did I tell you about ...', or wants JARVIS to recover something "
        "it was told before — including facts from earlier sessions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Topic/keywords to search memory for.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10).",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, query: str, limit: int = 10, **_: Any) -> Dict[str, Any]:
        try:
            results = get_memory_service().recall(query, limit=limit)
            return {"results": results, "count": len(results)}
        except Exception as exc:
            return {"error": f"Failed to recall: {exc}", "results": [], "count": 0}


class ListMemoriesTool(Tool):
    """List the most recent memories."""

    name = "list_memories"
    description = (
        "List JARVIS recently stored memories, facts, or past conversation highlights. "
        "Use when the user asks 'what do you remember?', 'list what you know', "
        "or 'show me your memories'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of memories to return (default: 20).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "memories": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, limit: int = 20, **_: Any) -> Dict[str, Any]:
        try:
            memories = get_memory_service().recent(limit=limit)
            return {"memories": memories, "count": len(memories)}
        except Exception as exc:
            return {"error": f"Failed to list memories: {exc}", "memories": [], "count": 0}


class ForgetTool(Tool):
    """Remove memories by keyword or record ID."""

    name = "forget"
    description = (
        "Delete memories from JARVIS long-term memory. "
        "Use when the user says 'forget ...', 'forget what I said about ...', "
        "'delete that memory', or wants JARVIS to stop remembering something."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords describing what to forget.",
            },
            "record_id": {
                "type": "string",
                "description": "Optional specific memory record ID to delete.",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "forgotten": {"type": "boolean"},
            "removed": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, query: str = "", record_id: str = "", **_: Any) -> Dict[str, Any]:
        try:
            return get_memory_service().forget(query, record_id)
        except Exception as exc:
            return {"forgotten": False, "removed": 0, "error": f"Failed to forget: {exc}"}


__all__ = ["RememberTool", "RecallTool", "ListMemoriesTool", "ForgetTool"]