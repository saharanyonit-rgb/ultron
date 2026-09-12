"""Unrestricted command execution for JARVIS — full system access.

Executes any system command without restrictions.
This tool gives JARVIS complete control over the PC.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.execute")


@dataclass
class ExecuteResult:
    """Result of command execution."""
    command: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }


class ExecuteCommand(Tool):
    """Execute any system command — full unrestricted access."""

    name = "execute_command"
    description = (
        "Execute any system command with full access. "
        "Runs via cmd.exe on Windows. Returns stdout, stderr, and exit code. "
        "Use this for running any program, script, or system operation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default 60.",
                "default": 60,
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for the command.",
            },
        },
        "required": ["command"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "success": {"type": "boolean"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "exit_code": {"type": "integer"},
            "duration_ms": {"type": "number"},
        },
    }
    mutates = True

    def run(self, command: str, timeout: int = 60, working_directory: str | None = None, **_: Any) -> Dict[str, Any]:
        start = time.time()
        try:
            use_shell = sys.platform == "win32"
            process = subprocess.Popen(
                command,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_directory,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                duration = (time.time() - start) * 1000
                return {
                    "command": command,
                    "success": False,
                    "stdout": "",
                    "stderr": f"Timed out after {timeout}s",
                    "exit_code": -1,
                    "duration_ms": duration,
                }

            duration = (time.time() - start) * 1000
            success = process.returncode == 0

            # Truncate very long output
            max_len = 50000
            if len(stdout) > max_len:
                stdout = stdout[:max_len] + "\n... (truncated)"
            if len(stderr) > max_len:
                stderr = stderr[:max_len] + "\n... (truncated)"

            return {
                "command": command,
                "success": success,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "exit_code": process.returncode,
                "duration_ms": duration,
            }

        except Exception as e:
            duration = (time.time() - start) * 1000
            return {
                "command": command,
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": duration,
            }


class ExecutePowerShell(Tool):
    """Execute PowerShell commands directly."""

    name = "execute_powershell"
    description = (
        "Execute a PowerShell command directly. "
        "Useful for Windows-specific operations, WMI queries, and system management."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The PowerShell command to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default 60.",
                "default": 60,
            },
        },
        "required": ["command"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "success": {"type": "boolean"},
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "exit_code": {"type": "integer"},
            "duration_ms": {"type": "number"},
        },
    }
    mutates = True

    def run(self, command: str, timeout: int = 60, **_: Any) -> Dict[str, Any]:
        start = time.time()
        try:
            if sys.platform == "win32":
                process = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                process = subprocess.run(
                    ["bash", "-c", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
            duration = (time.time() - start) * 1000
            max_len = 50000
            stdout = process.stdout[:max_len] if len(process.stdout) > max_len else process.stdout
            stderr = process.stderr[:max_len] if len(process.stderr) > max_len else process.stderr

            return {
                "command": command,
                "success": process.returncode == 0,
                "stdout": stdout.strip(),
                "stderr": stderr.strip(),
                "exit_code": process.returncode,
                "duration_ms": duration,
            }
        except Exception as e:
            duration = (time.time() - start) * 1000
            return {
                "command": command,
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": duration,
            }


__all__ = [
    "ExecuteCommand",
    "ExecutePowerShell",
]
