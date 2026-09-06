"""V1 file tools: read, create, search."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ultron.tools.base import Tool


def _iso(mtime_seconds: float) -> str:
    return datetime.fromtimestamp(mtime_seconds, tz=timezone.utc).isoformat()


class ReadFile(Tool):
    name = "read_file"
    description = "Read a text file and return its contents, size and last-modified time."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path of the file to read.",
            },
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "size": {"type": "integer"},
            "mtime_iso": {"type": "string"},
            "encoding": {"type": "string"},
        },
    }

    def run(self, path: str, **_: Any) -> Dict[str, Any]:
        target = Path(path).expanduser()
        if not target.is_file():
            return {"error": f"file not found: {target}"}
        try:
            data = target.read_bytes()
            for enc in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    content = data.decode(enc)
                    encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return {"error": f"file is not readable as text: {target}"}
        except OSError as exc:
            return {"error": f"could not read {target}: {exc}"}
        stat = target.stat()
        return {
            "content": content,
            "size": stat.st_size,
            "mtime_iso": _iso(stat.st_mtime),
            "encoding": encoding,
        }


class CreateFile(Tool):
    name = "create_file"
    description = (
        "Create a text file. Fails (without writing) if the file already exists "
        "unless overwrite=true."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path of the file to create."},
            "content": {"type": "string", "description": "Text content to write."},
            "overwrite": {
                "type": "boolean",
                "description": "Allow overwriting an existing file. Default false.",
            },
        },
        "required": ["path", "content"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "bytes_written": {"type": "integer"},
            "created": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, path: str, content: str = "", overwrite: bool = False, **_: Any) -> Dict[str, Any]:
        target = Path(path).expanduser()
        if target.exists() and not overwrite:
            return {"error": f"file already exists (use overwrite=true to replace): {target}"}
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            written = target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return {"error": f"could not write {target}: {exc}"}
        return {"path": str(target), "bytes_written": written, "created": not target.exists()}


class SearchFiles(Tool):
    name = "search_files"
    description = (
        "Search a directory for files matching a glob pattern "
        "(e.g. '**/*.py', '*.md'). Case-insensitive on Windows."
    )
    parameters = {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Absolute directory to search in."},
            "pattern": {"type": "string", "description": "Glob pattern relative to directory."},
            "max_results": {
                "type": "integer",
                "description": "Cap on matches returned. Default 100.",
            },
        },
        "required": ["directory", "pattern"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "matches": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }

    def run(self, directory: str, pattern: str, max_results: int = 100, **_: Any) -> Dict[str, Any]:
        base = Path(directory).expanduser()
        if not base.is_dir():
            return {"error": f"directory not found: {base}"}
        matches: List[str] = []
        try:
            for entry in base.glob(pattern):
                if entry.is_file():
                    matches.append(str(entry))
                    if len(matches) >= max_results:
                        return {
                            "matches": matches,
                            "count": len(matches),
                            "truncated": True,
                        }
        except (OSError, ValueError) as exc:
            return {"error": f"search failed in {base}: {exc}"}
        return {"matches": matches, "count": len(matches), "truncated": False}
