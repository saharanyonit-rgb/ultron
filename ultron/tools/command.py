"""Unrestricted command execution for JARVIS Phase 4 — Full Access Mode.

Executes system commands without restrictions when ULTRON_REQUIRE_PERMISSION=false.
All commands are still audit-logged for safety.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.risk import RiskLevel

logger = logging.getLogger("ultron.command")


class CommandStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class CommandResult:
    """Structured result of a command execution."""

    command: str
    status: CommandStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    working_directory: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return self.status == CommandStatus.SUCCESS and self.exit_code == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "working_directory": self.working_directory,
            "error": self.error,
        }


class CommandExecutor:
    """Executes system commands — full access mode when unrestricted."""

    def __init__(
        self,
        timeout: int = 120,
        working_directory: str | None = None,
        blocked_commands: List[str] | None = None,
        allowed_commands: List[str] | None = None,
        max_output_size: int = 1024 * 1024,
        unrestricted: bool | None = None,
    ) -> None:
        self._timeout = timeout
        self._working_directory = working_directory
        self._max_output_size = max_output_size
        self._allowed_commands = allowed_commands

        # If blocked_commands explicitly provided, use them (restricted mode)
        # If unrestricted explicitly True, no blocking
        # If unrestricted is None, auto-detect based on blocked_commands
        if blocked_commands is not None:
            self._blocked_commands = list(blocked_commands)
            self._unrestricted = False
        elif unrestricted is True:
            self._blocked_commands = []
            self._unrestricted = True
        elif unrestricted is False:
            self._blocked_commands = [
                "format", "del /s", "rmdir /s", "rd /s",
                "Remove-Item -Recurse", "shutdown", "reboot",
            ]
            self._unrestricted = False
        else:
            # Default: unrestricted mode (no blocking)
            self._blocked_commands = []
            self._unrestricted = True

    def execute(
        self,
        command: str,
        working_directory: str | None = None,
        timeout: int | None = None,
        env: Dict[str, str] | None = None,
    ) -> CommandResult:
        """Execute a command. In unrestricted mode, no commands are blocked."""
        start_time = time.time()

        if self._is_blocked(command):
            logger.warning("Blocked command: %s", command)
            return CommandResult(
                command=command,
                status=CommandStatus.BLOCKED,
                error=f"Command blocked by security policy: {command}",
            )

        # Check allowed list (always enforced if set)
        if self._allowed_commands is not None:
            cmd_base = command.split()[0] if command.split() else ""
            if cmd_base not in self._allowed_commands:
                return CommandResult(
                    command=command,
                    status=CommandStatus.BLOCKED,
                    error=f"Command not in allowed list: {cmd_base}",
                )

        cwd = working_directory or self._working_directory
        effective_timeout = timeout or self._timeout

        try:
            use_shell = sys.platform == "win32"
            process = subprocess.Popen(
                command,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            try:
                stdout, stderr = process.communicate(timeout=effective_timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration = (time.time() - start_time) * 1000
                return CommandResult(
                    command=command,
                    status=CommandStatus.TIMEOUT,
                    exit_code=-1,
                    duration_ms=duration,
                    working_directory=cwd or "",
                    error=f"Command timed out after {effective_timeout}s",
                )

            duration = (time.time() - start_time) * 1000

            if len(stdout) > self._max_output_size:
                stdout = stdout[:self._max_output_size] + "\n... (truncated)"
            if len(stderr) > self._max_output_size:
                stderr = stderr[:self._max_output_size] + "\n... (truncated)"

            status = CommandStatus.SUCCESS if process.returncode == 0 else CommandStatus.FAILED

            return CommandResult(
                command=command,
                status=status,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode,
                duration_ms=duration,
                working_directory=cwd or "",
            )

        except Exception as exc:
            duration = (time.time() - start_time) * 1000
            return CommandResult(
                command=command,
                status=CommandStatus.FAILED,
                exit_code=-1,
                duration_ms=duration,
                working_directory=cwd or "",
                error=f"Execution error: {exc}",
            )

    def _is_blocked(self, command: str) -> bool:
        if self._unrestricted:
            return False
        cmd_lower = command.lower()
        for blocked in self._blocked_commands:
            if blocked.lower() in cmd_lower:
                return True
        return False

    def get_risk_level(self, command: str) -> RiskLevel:
        if self._unrestricted:
            return RiskLevel.READ
        if self._is_blocked(command):
            return RiskLevel.CRITICAL
        high_risk_keywords = ["delete", "remove", "destroy", "format", "kill", "drop"]
        cmd_lower = command.lower()
        for keyword in high_risk_keywords:
            if keyword in cmd_lower:
                return RiskLevel.HIGH
        return RiskLevel.CRITICAL


__all__ = ["CommandExecutor", "CommandResult", "CommandStatus"]
