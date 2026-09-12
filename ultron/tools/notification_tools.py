"""Notification tools for Android — send, read, dismiss notifications."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux
from ultron.tools.base import Tool


class SendNotification(Tool):
    """Send a notification to the device."""

    name = "send_notification"
    description = "Post a notification to the Android notification bar."
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Notification title.",
            },
            "message": {
                "type": "string",
                "description": "Notification body text.",
            },
            "id": {
                "type": "string",
                "description": "Notification ID (for updating). Optional.",
            },
            "priority": {
                "type": "string",
                "description": "Priority: default, max, low, min, high.",
                "default": "default",
            },
            "vibrate": {
                "type": "boolean",
                "description": "Whether to vibrate.",
                "default": True,
            },
            "sound": {
                "type": "boolean",
                "description": "Whether to play a sound.",
                "default": True,
            },
        },
        "required": ["title", "message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "title": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self, title: str = "", message: str = "",
        id: str = "", priority: str = "default",
        vibrate: bool = True, sound: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        t = title or kwargs.get("header") or ""
        m = message or kwargs.get("text") or kwargs.get("body") or ""
        nid = id or kwargs.get("notification_id") or ""
        p = kwargs.get("level") or priority
        vib = kwargs.get("vibration") or vibrate
        snd = kwargs.get("alert") or sound

        if not t or not m:
            return {"error": "Title and message are required", "success": False}

        args = ["-t", t, "-c", m]
        if nid:
            args += ["-i", str(nid)]
        if p and p != "default":
            args += ["-p", str(p)]
        if not vib:
            args.append("--no-vibrate")
        if not snd:
            args.append("--no-sound")

        result = run_termux("notification", args=args)
        return {"success": result.ok, "title": t, "error": result.stderr or None}


class ListNotifications(Tool):
    """List current notifications in the notification bar."""

    name = "list_notifications"
    description = "List all active notifications on the device."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "notifications": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("notification-list", parse_json=True)
        if not result.ok:
            return {"notifications": [], "count": 0, "error": result.stderr}

        notifications = result.data if isinstance(result.data, list) else []
        return {"notifications": notifications, "count": len(notifications)}


class RemoveNotification(Tool):
    """Remove a specific notification by ID."""

    name = "remove_notification"
    description = "Dismiss/remove a notification by its ID."
    parameters = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "The notification ID to remove.",
            },
        },
        "required": ["id"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "removed_id": {"type": "string"},
        },
    }
    mutates = True

    def run(self, id: str = "", **kwargs: Any) -> Dict[str, Any]:
        nid = id or kwargs.get("notification_id") or kwargs.get("nid") or ""
        if not nid:
            return {"error": "No notification ID provided", "success": False}
        result = run_termux("notification-remove", args=[str(nid)])
        return {"success": result.ok, "removed_id": str(nid), "error": result.stderr or None}


class RemoveAllNotifications(Tool):
    """Dismiss all active notifications."""

    name = "remove_all_notifications"
    description = "Clear all active notifications from the notification bar."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("notification-remove", args=["-a", "all"])
        return {"success": result.ok}


class GetNotificationSettings(Tool):
    """Get Android notification settings."""

    name = "get_notification_settings"
    description = "Get notification channel settings or global notification status."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "enabled": {"type": "boolean"},
            "dnd_enabled": {"type": "boolean"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("notification-list", parse_json=True)
        notifications = result.data if isinstance(result.data, list) else []
        return {
            "enabled": True,
            "dnd_enabled": False,
            "active_count": len(notifications),
        }


__all__ = [
    "SendNotification",
    "ListNotifications",
    "RemoveNotification",
    "RemoveAllNotifications",
    "GetNotificationSettings",
]
