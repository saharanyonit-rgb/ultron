"""Contact management tools for Android — list, search, add contacts."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux
from ultron.tools.base import Tool


class ListContacts(Tool):
    """List all contacts on the phone."""

    name = "list_contacts"
    description = "List all contacts stored on the Android device."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "contacts": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("contact-list", parse_json=True)
        if not result.ok:
            return {"contacts": [], "count": 0, "error": result.stderr}

        contacts = result.data if isinstance(result.data, list) else []
        return {"contacts": contacts, "count": len(contacts)}


class SearchContact(Tool):
    """Search contacts by name."""

    name = "search_contact"
    description = "Search contacts by name or number."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query — name or phone number to search for.",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "contacts": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        q = query or kwargs.get("name") or kwargs.get("search") or ""
        if not q:
            return {"contacts": [], "count": 0, "error": "No search query provided"}

        result = run_termux("contact-list", parse_json=True)
        if not result.ok:
            return {"contacts": [], "count": 0, "error": result.stderr}

        contacts = result.data if isinstance(result.data, list) else []
        q_lower = q.lower()
        matched = [
            c for c in contacts
            if q_lower in c.get("name", "").lower() or q_lower in c.get("number", "").lower()
        ]
        return {"contacts": matched, "count": len(matched)}


class AddContact(Tool):
    """Add a new contact to the phone."""

    name = "add_contact"
    description = "Add a new contact with name and phone number."
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Contact name.",
            },
            "number": {
                "type": "string",
                "description": "Phone number.",
            },
        },
        "required": ["name", "number"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "name": {"type": "string"},
            "number": {"type": "string"},
        },
    }
    mutates = True

    def run(self, name: str = "", number: str = "", **kwargs: Any) -> Dict[str, Any]:
        n = name or kwargs.get("contact_name") or ""
        num = number or kwargs.get("phone") or kwargs.get("number") or ""
        if not n or not num:
            return {"error": "Both name and number are required", "success": False}

        result = run_termux("contact-add", args=["-n", n, "-p", num])
        return {
            "success": result.ok,
            "name": n,
            "number": num,
            "error": result.stderr or None,
        }


class DeleteContact(Tool):
    """Delete a contact from the phone."""

    name = "delete_contact"
    description = "Delete a contact by name or number."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Contact name or number to delete.",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "deleted": {"type": "string"},
        },
    }
    mutates = True

    def run(self, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        q = query or kwargs.get("name") or kwargs.get("contact") or ""
        if not q:
            return {"error": "No contact specified", "success": False}

        # First find the contact
        search_result = run_termux("contact-list", parse_json=True)
        if not search_result.ok:
            return {"success": False, "error": search_result.stderr}

        contacts = search_result.data if isinstance(search_result.data, list) else []
        matched = [
            c for c in contacts
            if q.lower() in c.get("name", "").lower() or q in c.get("number", "")
        ]

        if not matched:
            return {"success": False, "error": f"No contact found matching '{q}'"}

        contact_id = matched[0].get("id", "")
        if contact_id:
            result = run_termux("contact-delete", args=[str(contact_id)])
            return {"success": result.ok, "deleted": matched[0].get("name", q)}

        return {"success": False, "error": "Contact found but has no ID for deletion"}


__all__ = ["ListContacts", "SearchContact", "AddContact", "DeleteContact"]
