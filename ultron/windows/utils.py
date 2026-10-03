"""Windows-specific utilities for Ultron V1.

OS control helpers used by V1 tools.

NOT V2 PowerShell/CMD execution — keep V1 lean.
"""

from __future__ import annotations

import platform


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system() == "Windows"


def get_os_version() -> str:
    """Return OS version string."""
    return platform.version()


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    value: float = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"
