"""Desktop configuration management.

Stores configuration in %APPDATA%/JARVIS/ directory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


def get_app_data_dir() -> Path:
    """Get the JARVIS application data directory."""
    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    app_dir = Path(appdata) / "JARVIS"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_logs_dir() -> Path:
    """Get the JARVIS logs directory."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_config_path() -> Path:
    """Get the desktop configuration file path."""
    return get_app_data_dir() / "desktop_config.json"


@dataclass
class DesktopConfig:
    """Desktop application configuration."""

    # Window
    window_width: int = 1200
    window_height: int = 800
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    window_maximized: bool = False

    # Backend
    backend_port: int = 8080
    backend_host: str = "127.0.0.1"
    backend_start_timeout: int = 30
    auto_start_backend: bool = True

    # Behavior
    close_to_tray: bool = True
    start_minimized: bool = False
    start_with_windows: bool = False
    show_notifications: bool = True

    # Appearance
    theme: str = "dark"
    accent_color: str = "#3dffb0"

    def save(self) -> None:
        """Save configuration to file."""
        config_path = get_config_path()
        config_path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> DesktopConfig:
        """Load configuration from file, or return defaults."""
        config_path = get_config_path()
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()
