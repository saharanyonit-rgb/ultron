"""Windows-specific utilities for Ultron V1.

OS control helpers used by V1 tools.

NOT V2 PowerShell/CMD execution — keep V1 lean.
"""

from __future__ import annotations

import platform
from typing import Any


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def get_os_version() -> str:
    """Return OS version string."""
    return platform.version()


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"
