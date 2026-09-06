"""Unrestricted filesystem operations for JARVIS — full disk access.

Provides complete file system access without restrictions.
Can read, write, delete, copy, move any file on the system.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

from ultron.tools.base import Tool


class ReadFileUnrestricted(Tool):
    """Read any file on the system."""

    name = "read_file_full"
    description = "Read the contents of any file on the system. Full access, no restrictions."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file."},
            "encoding": {"type": "string", "default": "utf-8", "description": "File encoding."},
            "max_lines": {"type": "integer", "default": 5000, "description": "Max lines to read."},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "size": {"type": "integer"},
            "truncated": {"type": "boolean"},
        },
    }

    def run(self, path: str, encoding: str = "utf-8", max_lines: int = 5000, **_: Any) -> Dict[str, Any]:
        try:
            p = Path(path).expanduser()
            if not p.is_file():
                return {"error": f"Not a file: {path}"}
            stat = p.stat()
            content = p.read_text(encoding=encoding, errors="replace")
            lines = content.splitlines()
            truncated = len(lines) > max_lines
            if truncated:
                content = "\n".join(lines[:max_lines]) + f"\n... ({len(lines)} total lines, truncated)"
            return {
                "path": str(p),
                "content": content,
                "size": stat.st_size,
                "truncated": truncated,
            }
        except Exception as e:
            return {"error": str(e)}


class WriteFileUnrestricted(Tool):
    """Write any file on the system."""

    name = "write_file_full"
    description = "Write content to any file on the system. Creates parent directories automatically."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file."},
            "content": {"type": "string", "description": "Content to write."},
            "append": {"type": "boolean", "default": False, "description": "Append to file instead of overwrite."},
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

    def run(self, path: str, content: str, append: bool = False, **_: Any) -> Dict[str, Any]:
        try:
            p = Path(path).expanduser()
            existed = p.exists()
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(p, mode, encoding="utf-8") as f:
                f.write(content)
            size = len(content.encode("utf-8"))
            return {
                "path": str(p),
                "bytes_written": size,
                "created": not existed,
            }
        except Exception as e:
            return {"error": str(e)}


class ListDirectoryUnrestricted(Tool):
    """List any directory on the system."""

    name = "list_directory_full"
    description = "List the contents of any directory on the system."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list."},
            "pattern": {"type": "string", "description": "Optional glob pattern (e.g. '*.py')."},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "entries": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, path: str, pattern: str | None = None, **_: Any) -> Dict[str, Any]:
        try:
            p = Path(path).expanduser()
            if not p.is_dir():
                return {"error": f"Not a directory: {path}"}
            entries = []
            items = p.glob(pattern) if pattern else p.iterdir()
            for item in sorted(items):
                try:
                    stat = item.stat()
                    entries.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else 0,
                        "modified": stat.st_mtime,
                    })
                except PermissionError:
                    entries.append({"name": item.name, "type": "unknown", "error": "permission denied"})
            return {"path": str(p), "entries": entries, "count": len(entries)}
        except Exception as e:
            return {"error": str(e)}


class DeleteFileUnrestricted(Tool):
    """Delete any file or directory."""

    name = "delete_file_full"
    description = "Delete any file or directory. USE WITH CAUTION. No undo."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete."},
            "recursive": {"type": "boolean", "default": False, "description": "Delete directories recursively."},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "deleted": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, path: str, recursive: bool = False, **_: Any) -> Dict[str, Any]:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return {"error": f"Path does not exist: {path}"}
            if p.is_dir():
                if recursive:
                    shutil.rmtree(p)
                else:
                    p.rmdir()
            else:
                p.unlink()
            return {"path": str(p), "deleted": True}
        except Exception as e:
            return {"error": str(e)}


class CopyFileUnrestricted(Tool):
    """Copy files or directories."""

    name = "copy_file_full"
    description = "Copy a file or directory to a new location."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path."},
            "destination": {"type": "string", "description": "Destination path."},
        },
        "required": ["source", "destination"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
            "copied": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, source: str, destination: str, **_: Any) -> Dict[str, Any]:
        try:
            src = Path(source).expanduser()
            dst = Path(destination).expanduser()
            if not src.exists():
                return {"error": f"Source does not exist: {source}"}
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
            return {"source": str(src), "destination": str(dst), "copied": True}
        except Exception as e:
            return {"error": str(e)}


class MoveFileUnrestricted(Tool):
    """Move/rename files or directories."""

    name = "move_file_full"
    description = "Move or rename a file or directory."
    parameters = {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path."},
            "destination": {"type": "string", "description": "Destination path."},
        },
        "required": ["source", "destination"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
            "moved": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, source: str, destination: str, **_: Any) -> Dict[str, Any]:
        try:
            src = Path(source).expanduser()
            dst = Path(destination).expanduser()
            if not src.exists():
                return {"error": f"Source does not exist: {source}"}
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {"source": str(src), "destination": str(dst), "moved": True}
        except Exception as e:
            return {"error": str(e)}


class SearchFilesUnrestricted(Tool):
    """Search for files by name or content pattern."""

    name = "search_files_full"
    description = "Search for files by name pattern or content. Full system access."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Root directory to search from."},
            "pattern": {"type": "string", "description": "Glob pattern for filenames (e.g. '*.py', '*.txt')."},
            "content": {"type": "string", "description": "Text to search for inside files."},
            "max_results": {"type": "integer", "default": 50, "description": "Max results to return."},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, path: str, pattern: str | None = None, content: str | None = None,
            max_results: int = 50, **_: Any) -> Dict[str, Any]:
        try:
            root = Path(path).expanduser()
            if not root.is_dir():
                return {"error": f"Not a directory: {path}"}

            results = []
            glob_pattern = pattern or "**/*"

            for file_path in root.glob(glob_pattern):
                if len(results) >= max_results:
                    break
                if not file_path.is_file():
                    continue

                if content:
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="replace")
                        if content.lower() in text.lower():
                            results.append({"path": str(file_path), "name": file_path.name})
                    except Exception:
                        continue
                else:
                    results.append({"path": str(file_path), "name": file_path.name})

            return {"results": results, "count": len(results)}
        except Exception as e:
            return {"error": str(e)}


__all__ = [
    "ReadFileUnrestricted",
    "WriteFileUnrestricted",
    "ListDirectoryUnrestricted",
    "DeleteFileUnrestricted",
    "CopyFileUnrestricted",
    "MoveFileUnrestricted",
    "SearchFilesUnrestricted",
]
