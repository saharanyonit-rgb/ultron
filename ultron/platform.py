"""Cross-platform detection and abstraction for ULTRON.

Detects the current platform (Windows, Linux, macOS, Android/Termux)
and provides helpers to abstract OS-specific behavior.
"""

from __future__ import annotations

import os
import platform
import sys
from enum import Enum
from typing import Optional


class Platform(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"


_platform: Optional[Platform] = None


def detect_platform() -> Platform:
    """Detect the current platform once and cache the result."""
    global _platform
    if _platform is not None:
        return _platform

    system = platform.system().lower()

    # Check for Android/Termux first (Linux kernel but distinct environment)
    if system == "linux":
        # Termux sets PREFIX=/data/data/com.termux/files/usr
        if os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
            _platform = Platform.ANDROID
        # Also check for Android properties
        elif os.path.exists("/system/build.prop"):
            _platform = Platform.ANDROID
        else:
            _platform = Platform.LINUX
    elif system == "darwin":
        _platform = Platform.MACOS
    elif system == "windows":
        _platform = Platform.WINDOWS
    else:
        _platform = Platform.LINUX  # fallback

    return _platform


def is_windows() -> bool:
    return detect_platform() == Platform.WINDOWS


def is_android() -> bool:
    return detect_platform() == Platform.ANDROID


def is_linux() -> bool:
    return detect_platform() in (Platform.LINUX, Platform.ANDROID)


def is_macos() -> bool:
    return detect_platform() == Platform.MACOS


def is_posix() -> bool:
    return detect_platform() in (Platform.LINUX, Platform.ANDROID, Platform.MACOS)


def platform_name() -> str:
    return detect_platform().value
