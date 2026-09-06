"""Windows helpers shared by tools — subprocess + built-in PowerShell only.

Deliberately zero pip dependencies: everything here uses what ships with
Windows 10/11 (PowerShell 5.1, System.Drawing, System.Windows.Forms).
"""

from __future__ import annotations

import subprocess
from typing import List, Optional


def run_powershell(
    script: str,
    timeout: int = 60,
    text_output: bool = False,
) -> subprocess.CompletedProcess:
    """Run a PowerShell snippet and capture output.

    `text_output=True` forces UTF-8 console encoding so non-ASCII text
    survives the round trip.
    """
    if text_output:
        script = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\n" + script
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def ps_quote(value: str) -> str:
    """Escape a value for safe embedding in single quotes inside PS."""
    return "'" + value.replace("'", "''") + "'"


def b64(text: str) -> str:
    """UTF-8 base64 — used to shuttle text through PowerShell safely."""
    import base64

    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def unb64(data: str) -> str:
    import base64

    return base64.b64decode(data).decode("utf-8")


def ps_stdout(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout.strip() if proc.stdout else ""


def ps_error(proc: subprocess.CompletedProcess) -> str:
    parts = [s for s in (proc.stdout or "", proc.stderr or "") if s]
    return " | ".join(parts).strip()


def ps_ok(proc: subprocess.CompletedProcess) -> bool:
    return proc.returncode == 0
