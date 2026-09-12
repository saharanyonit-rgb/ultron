"""System shutdown tool — cross-platform (Windows shutdown, Linux/Android reboot/poweroff)."""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict

from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.shutdown")


@dataclass
class ShutdownResult:
    """Result of shutdown operation."""
    success: bool
    message: str
    exit_code: int = 0


class ShutdownTool(Tool):
    """Initiate system shutdown using the platform-appropriate mechanism."""

    name = "system_shutdown"
    description = (
        "Initiate system shutdown or reboot. "
        "This is a CRITICAL-risk action that requires user confirmation. "
        "On Windows uses shutdown command; on Linux/Android uses shutdown/reboot."
    )
    parameters = {
        "type": "object",
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": "If True, skip confirmation. Default False always requires confirmation.",
                "default": False,
            },
            "reboot": {
                "type": "boolean",
                "description": "If True, reboot instead of shutdown. Default False.",
                "default": False,
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
        },
    }
    mutates = True

    def run(self, confirm: bool = False, reboot: bool = False, **_: Any) -> Dict[str, Any]:
        if not confirm:
            return {
                "success": False,
                "message": "Shutdown confirmation required through permission system",
            }

        try:
            if sys.platform == "win32":
                cmd = ["shutdown", "/r" if reboot else "/s", "/t", "0"]
            else:
                cmd = ["reboot"] if reboot else ["shutdown", "-h", "now"]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            success = result.returncode == 0
            action = "reboot" if reboot else "shutdown"
            message = (
                f"System {action} initiated successfully."
                if success
                else f"System {action} failed: {result.stderr.strip() or result.stdout.strip()}"
            )
            return {"success": success, "message": message}
        except Exception as e:
            logger.error("Shutdown error: %s", e)
            return {"success": False, "message": f"Shutdown error: {str(e)}"}


__all__ = ["ShutdownTool", "ShutdownResult"]
