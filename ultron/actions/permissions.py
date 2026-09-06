"""Secure permission gate — V2 permissioned tool execution.

Extends the Phase 1 PermissionGate with confirmation for mutating tools.
Uses a callback-based confirmation so the CLI can use input() and other
frontends can use their own mechanisms.

Phase 1 PermissionGate is preserved and used as the base class.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from ultron.actions import PermissionDecision, PermissionGate

if False:  # TYPE_CHECKING — avoids circular import
    from ultron.tools.base import Tool

logger = logging.getLogger("ultron.actions.permissions")

# Callback signature: (tool_name, arguments) -> bool (True = allow)
ConfirmCallback = Callable[[str, dict[str, Any]], bool]


class SecurePermissionGate(PermissionGate):
    """V2 permission gate that requires confirmation for mutating tools.

    Read-only tools pass through automatically.
    Mutating tools invoke the confirmation callback.
    """

    def __init__(self, confirm: Optional[ConfirmCallback] = None) -> None:
        self._confirm = confirm or self._default_confirm

    def check(self, tool: "Tool", arguments: dict[str, Any]) -> PermissionDecision:
        """Check permissions with confirmation for mutating tools."""
        if not getattr(tool, "mutates", False):
            return PermissionDecision(allowed=True, reason="read-only action")

        # Mutating tool — ask for confirmation
        tool_name = getattr(tool, "name", "unknown")
        logger.info("Permission requested for mutating tool: %s", tool_name)

        try:
            allowed = self._confirm(tool_name, arguments)
        except Exception as exc:
            logger.error("Confirmation callback failed: %s", exc)
            return PermissionDecision(
                allowed=False,
                reason=f"Confirmation failed: {type(exc).__name__}",
            )

        if allowed:
            logger.info("Permission GRANTED for %s", tool_name)
            return PermissionDecision(allowed=True, reason="user confirmed mutating action")
        else:
            logger.info("Permission DENIED for %s", tool_name)
            return PermissionDecision(allowed=False, reason="user denied mutating action")

    @staticmethod
    def _default_confirm(tool_name: str, arguments: dict[str, Any]) -> bool:
        """Default confirmation: always deny (safe default)."""
        return False


class CLIPermissionGate(SecurePermissionGate):
    """Permission gate that uses terminal input() for confirmation."""

    def __init__(self) -> None:
        super().__init__(confirm=self._cli_confirm)

    @staticmethod
    def _cli_confirm(tool_name: str, arguments: dict[str, Any]) -> bool:
        """Ask the user via terminal input."""
        args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items()) if arguments else "(no args)"
        prompt = f"\n  [permission] Allow '{tool_name}' ({args_str})? [y/N]: "
        try:
            response = input(prompt).strip().lower()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False


__all__ = ["SecurePermissionGate", "CLIPermissionGate", "ConfirmCallback"]
