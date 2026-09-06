"""Controlled filesystem tools for JARVIS Phase 4.

Provides path validation, allowed-root restrictions, traversal protection,
and structured errors for all filesystem operations.

Security:
  - All paths are resolved to absolute form
  - Traversal attacks (../) are blocked
  - Operations outside allowed roots are rejected
  - All operations are classified by risk level
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.risk import RiskLevel


class FilesystemError(Exception):
    """Base exception for filesystem operations."""


class PathValidationError(FilesystemError):
    """Raised when a path fails validation."""


class AccessDeniedError(FilesystemError):
    """Raised when an operation is outside allowed roots."""


class FilesystemTool:
    """Controlled filesystem tool with security enforcement."""

    def __init__(
        self,
        allowed_roots: List[str | Path] | None = None,
        workspace: str | Path | None = None,
    ) -> None:
        self._workspace = Path(workspace) if workspace else Path.cwd()
        self._allowed_roots: List[Path] = []

        if allowed_roots:
            for root in allowed_roots:
                self._allowed_roots.append(Path(root).resolve())
        else:
            # Default: workspace and its parents up to 2 levels
            self._allowed_roots = [
                self._workspace.resolve(),
                self._workspace.resolve().parent,
            ]

    @property
    def workspace(self) -> Path:
        return self._workspace

    @property
    def allowed_roots(self) -> List[Path]:
        return list(self._allowed_roots)

    def validate_path(self, path: str | Path) -> Path:
        """Validate and resolve a path. Raises on invalid paths."""
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as exc:
            raise PathValidationError(f"Invalid path: {path}") from exc

        # Check for traversal attacks
        if ".." in str(path):
            raise PathValidationError(f"Path traversal detected: {path}")

        return resolved

    def check_access(self, path: Path) -> bool:
        """Check if a path is within allowed roots."""
        resolved = path.resolve()
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def require_access(self, path: Path) -> Path:
        """Validate path and check access. Raises on denial."""
        resolved = self.validate_path(path)
        if not self.check_access(resolved):
            raise AccessDeniedError(
                f"Access denied: {resolved} is outside allowed roots "
                f"{[str(r) for r in self._allowed_roots]}"
            )
        return resolved

    def list_directory(self, path: str | Path = ".") -> Dict[str, Any]:
        """List directory contents with metadata."""
        resolved = self.require_access(path)
        if not resolved.is_dir():
            return {"error": f"Not a directory: {resolved}"}

        entries = []
        for entry in sorted(resolved.iterdir()):
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })

        return {"path": str(resolved), "entries": entries, "count": len(entries)}

    def read_file(self, path: str | Path, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read a text file."""
        resolved = self.require_access(path)
        if not resolved.is_file():
            return {"error": f"Not a file: {resolved}"}

        try:
            content = resolved.read_text(encoding=encoding)
            stat = resolved.stat()
            return {
                "path": str(resolved),
                "content": content,
                "size": stat.st_size,
                "encoding": encoding,
            }
        except UnicodeDecodeError as exc:
            return {"error": f"Encoding error: {exc}"}
        except OSError as exc:
            return {"error": f"Read error: {exc}"}

    def create_file(
        self,
        path: str | Path,
        content: str,
        overwrite: bool = False,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Create or overwrite a text file."""
        resolved = self.require_access(path)

        if resolved.exists() and not overwrite:
            return {"error": f"File exists and overwrite=False: {resolved}"}

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding=encoding)
            return {
                "path": str(resolved),
                "created": True,
                "size": len(content.encode(encoding)),
            }
        except OSError as exc:
            return {"error": f"Write error: {exc}"}

    def modify_file(
        self,
        path: str | Path,
        content: str,
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Modify an existing file (must exist)."""
        resolved = self.require_access(path)
        if not resolved.exists():
            return {"error": f"File does not exist: {resolved}"}

        try:
            resolved.write_text(content, encoding=encoding)
            return {
                "path": str(resolved),
                "modified": True,
                "size": len(content.encode(encoding)),
            }
        except OSError as exc:
            return {"error": f"Modify error: {exc}"}

    def rename_file(self, old_path: str | Path, new_path: str | Path) -> Dict[str, Any]:
        """Rename/move a file."""
        old_resolved = self.require_access(old_path)
        new_resolved = self.require_access(new_path)

        if not old_resolved.exists():
            return {"error": f"Source does not exist: {old_resolved}"}
        if new_resolved.exists():
            return {"error": f"Destination exists: {new_resolved}"}

        try:
            old_resolved.rename(new_resolved)
            return {
                "old_path": str(old_resolved),
                "new_path": str(new_resolved),
                "renamed": True,
            }
        except OSError as exc:
            return {"error": f"Rename error: {exc}"}

    def delete_file(self, path: str | Path) -> Dict[str, Any]:
        """Delete a file (not directories)."""
        resolved = self.require_access(path)
        if not resolved.is_file():
            return {"error": f"Not a file: {resolved}"}

        try:
            resolved.unlink()
            return {"path": str(resolved), "deleted": True}
        except OSError as exc:
            return {"error": f"Delete error: {exc}"}

    def get_metadata(self, path: str | Path) -> Dict[str, Any]:
        """Get file/directory metadata."""
        resolved = self.require_access(path)
        if not resolved.exists():
            return {"error": f"Path does not exist: {resolved}"}

        stat = resolved.stat()
        return {
            "path": str(resolved),
            "type": "directory" if resolved.is_dir() else "file",
            "size": stat.st_size,
            "exists": True,
        }

    def get_risk_level(self, operation: str) -> RiskLevel:
        """Get the risk level for a filesystem operation."""
        risk_map = {
            "list": RiskLevel.READ,
            "read": RiskLevel.READ,
            "metadata": RiskLevel.READ,
            "create": RiskLevel.MEDIUM,
            "modify": RiskLevel.MEDIUM,
            "rename": RiskLevel.HIGH,
            "delete": RiskLevel.HIGH,
        }
        return risk_map.get(operation, RiskLevel.MEDIUM)


__all__ = [
    "FilesystemTool",
    "FilesystemError",
    "PathValidationError",
    "AccessDeniedError",
]
