"""Static File Server Utilities & Caching for JARVIS Web Server.

Provides MIME types, path validation, ETag caching, and gzip compression.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger("ultron.web_static")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".eot": "application/vnd.ms-fontobject",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".webp": "image/webp",
}

STATIC_CACHE_MAX_AGE = 3600
API_CACHE_CONTROL = "no-cache, no-store, must-revalidate"


def get_mime_type(file_path: Path) -> str:
    """Get MIME type for static file."""
    return MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")


def generate_etag(data: bytes) -> str:
    """Generate MD5 ETag for content caching."""
    return hashlib.md5(data).hexdigest()


__all__ = [
    "FRONTEND_DIR",
    "MIME_TYPES",
    "STATIC_CACHE_MAX_AGE",
    "API_CACHE_CONTROL",
    "get_mime_type",
    "generate_etag",
]
