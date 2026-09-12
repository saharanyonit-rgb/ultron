"""Termux API wrapper — central utility for all termux-* commands.

All Android phone control tools delegate to this module.
Requires: Termux + termux-api package.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.tools.termux")

COMMAND_TIMEOUT = 15


@dataclass
class TermuxResult:
    """Structured result of a termux command."""
    command: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    data: Any = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"command": self.command, "success": self.ok, "returncode": self.returncode}
        if self.data is not None:
            d["data"] = self.data
        if self.stdout:
            d["stdout"] = self.stdout[:5000]
        if self.stderr:
            d["error"] = self.stderr[:2000]
        return d


def run_termux(
    subcommand: str,
    args: Optional[List[str]] = None,
    stdin_text: Optional[str] = None,
    timeout: int = COMMAND_TIMEOUT,
    parse_json: bool = False,
) -> TermuxResult:
    """Run a termux-* command and return a structured result."""
    cmd = ["termux-" + subcommand] + (args or [])
    cmd_str = " ".join(cmd)

    try:
        proc = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = TermuxResult(
            command=cmd_str,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
        if parse_json and proc.stdout.strip():
            try:
                result.data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                result.data = proc.stdout.strip()
        return result
    except FileNotFoundError:
        return TermuxResult(
            command=cmd_str,
            returncode=-1,
            stderr="termux-api not installed. Run: pkg install termux-api",
        )
    except subprocess.TimeoutExpired:
        return TermuxResult(
            command=cmd_str,
            returncode=-1,
            stderr=f"Command timed out after {timeout}s",
        )
    except Exception as e:
        return TermuxResult(command=cmd_str, returncode=-1, stderr=str(e))


def run_raw(
    args: List[str],
    timeout: int = COMMAND_TIMEOUT,
) -> TermuxResult:
    """Run an arbitrary shell command (not termux-*)."""
    cmd_str = " ".join(args)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return TermuxResult(
            command=cmd_str,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
    except FileNotFoundError:
        return TermuxResult(command=cmd_str, returncode=-1, stderr=f"Command not found: {args[0]}")
    except subprocess.TimeoutExpired:
        return TermuxResult(command=cmd_str, returncode=-1, stderr=f"Timed out after {timeout}s")
    except Exception as e:
        return TermuxResult(command=cmd_str, returncode=-1, stderr=str(e))


def run_input(keyevent: str) -> TermuxResult:
    """Run Android 'input' shell command (requires shell access)."""
    return run_raw(["input", keyevent], timeout=10)


def run_am(args: List[str]) -> TermuxResult:
    """Run an Android 'am' activity manager command."""
    return run_raw(["am"] + args, timeout=10)


def run_pm(args: List[str]) -> TermuxResult:
    """Run Android 'pm' package manager command."""
    return run_raw(["pm"] + args, timeout=10)


def run_settings(args: List[str]) -> TermuxResult:
    """Run Android 'settings' command."""
    return run_raw(["settings"] + args, timeout=10)


def run_dumpsys(args: List[str]) -> TermuxResult:
    """Run Android 'dumpsys' command."""
    return run_raw(["dumpsys"] + args, timeout=15)


def run_cmd(args: List[str]) -> TermuxResult:
    """Run any shell command."""
    return run_raw(args, timeout=15)


__all__ = [
    "TermuxResult",
    "run_termux",
    "run_raw",
    "run_input",
    "run_am",
    "run_pm",
    "run_settings",
    "run_dumpsys",
    "run_cmd",
]
