"""Application-wide logging configuration for Ultron / JARVIS.

A single, idempotent entry point: `configure_logging(level)`. The Brain,
Router, and ToolExecutor log through the `ultron.*` logger hierarchy; this
module attaches one handler to the `ultron` root and sets the level.

Secrets (anything that looks like `*_API_KEY=...` or `*_TOKEN=...`) are
replaced with `***REDACTED***` in formatted output. Keys are never logged
by callers because the formatter strips them at the boundary.
"""

from __future__ import annotations

import logging
import re
from typing import Final

LOGGER_NAME: Final[str] = "ultron"
_LEVELS: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Match KEY=VALUE for any var name containing KEY/TOKEN/SECRET/PASSWORD.
_SECRET_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*([^\s,;]+)"
)


class _SecretRedactingFormatter(logging.Formatter):
    """Formatter that redacts anything that looks like a secret assignment."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003 - std API
        rendered = super().format(record)
        return _SECRET_RE.sub(r"\1=***REDACTED***", rendered)


_CONFIGURED = False


def configure_logging(level: str | int = "INFO") -> logging.Logger:
    """Configure the `ultron` logger once. Safe to call multiple times."""
    global _CONFIGURED
    if isinstance(level, str):
        resolved = _LEVELS.get(level.upper(), logging.INFO)
    else:
        resolved = level

    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(resolved)

    if not _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(
            _SecretRedactingFormatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        root.addHandler(handler)
        root.propagate = False
        _CONFIGURED = True

    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the `ultron` hierarchy."""
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger", "LOGGER_NAME"]
