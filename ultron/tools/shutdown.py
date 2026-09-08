"""Windows shutdown tool for JARVIS.

Provides a dedicated, safe Windows shutdown mechanism using the standard
Windows shutdown API. This tool is specifically for system shutdown and
is registered with CRITICAL risk level requiring explicit user confirmation.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.shutdown")


@dataclass
class ShutdownResult:
    """Result of Windows shutdown operation."""
    success: bool
    message: str
    exit_code: int = 0


class ShutdownTool(Tool):
    """Initiate Windows system shutdown using the standard shutdown mechanism.

    Uses `shutdown /s /t 0` to request an immediate system shutdown.
    This tool has CRITICAL risk level and always requires user confirmation
    through the existing permission/policy system.

    The shutdown command is:
        shutdown /s /t 0

    This:
    - Shuts down the local computer immediately
    - Warns all logged-on users
    - Closes running applications with unsaved changes (prompting to save)
    - Transitions to power-off state when safe
    """

    name = "windows_shutdown"
    description = (
        "Initiate Windows system shutdown using the standard mechanism. "
        "This is a CRITICAL-risk action that requires user confirmation. "
        "Uses shutdown /s /t 0 for immediate shutdown request."
    )
    parameters = {
        "type": "object",
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": "If True, skip confirmation (for trusted paths). "
                               "Default False always requires confirmation.",
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

    def run(self, confirm: bool = False, **_: Any) -> Dict[str, Any]:
        """Execute Windows shutdown.

        Args:
            confirm: If True, skip the confirmation step. Default False always
                     requires confirmation through the permission system.

        Returns:
            Dict with success and message keys.
        """
        if not confirm:
            # Confirmation is always required through the permission system
            # When called directly, we return needing confirmation
            return {
                "success": False,
                "message": "Shutdown confirmation required through permission system",
            }

        try:
            result = subprocess.run(
                ["shutdown", "/s", "/t", "0"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            success = result.returncode == 0
            message = (
                "Windows shutdown initiated successfully."
                if success
                else f"Windows shutdown failed: {result.stderr.strip() or result.stdout.strip()}"
            )
            logger.info("Windows shutdown %s", "initiated" if success else "failed")
            return {
                "success": success,
                "message": message,
            }
        except Exception as e:
            logger.error("Windows shutdown error: %s", e)
            return {
                "success": False,
                "message": f"Windows shutdown error: {str(e)}",
            }


__all__ = [
    "ShutdownTool",
    "ShutdownResult",
]