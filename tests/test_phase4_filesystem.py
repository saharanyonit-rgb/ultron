"""Tests for controlled filesystem tools (Phase 4)."""

from __future__ import annotations

import pytest

from ultron.tools.filesystem import (
    FilesystemTool,
    FilesystemError,
    PathValidationError,
    AccessDeniedError,
)
from ultron.risk import RiskLevel


def test_list_directory(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "test.txt").write_text("hello")
    result = fs.list_directory(tmp_path)
    assert "entries" in result
    assert result["count"] == 1
    assert result["entries"][0]["name"] == "test.txt"


def test_list_directory_not_dir(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "file.txt").write_text("content")
    result = fs.list_directory(tmp_path / "file.txt")
    assert "error" in result


def test_read_file(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "test.txt").write_text("hello world")
    result = fs.read_file(tmp_path / "test.txt")
    assert result["content"] == "hello world"
    assert result["size"] == 11


def test_read_file_not_found(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    result = fs.read_file(tmp_path / "nonexistent.txt")
    assert "error" in result


def test_create_file(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    result = fs.create_file(tmp_path / "new.txt", "content")
    assert result["created"] is True
    assert (tmp_path / "new.txt").read_text() == "content"


def test_create_file_no_overwrite(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "existing.txt").write_text("old")
    result = fs.create_file(tmp_path / "existing.txt", "new", overwrite=False)
    assert "error" in result
    assert (tmp_path / "existing.txt").read_text() == "old"


def test_create_file_overwrite(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "existing.txt").write_text("old")
    result = fs.create_file(tmp_path / "existing.txt", "new", overwrite=True)
    assert result["created"] is True
    assert (tmp_path / "existing.txt").read_text() == "new"


def test_modify_file(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "file.txt").write_text("old")
    result = fs.modify_file(tmp_path / "file.txt", "new")
    assert result["modified"] is True
    assert (tmp_path / "file.txt").read_text() == "new"


def test_modify_file_not_found(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    result = fs.modify_file(tmp_path / "missing.txt", "content")
    assert "error" in result


def test_rename_file(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "old.txt").write_text("content")
    result = fs.rename_file(tmp_path / "old.txt", tmp_path / "new.txt")
    assert result["renamed"] is True
    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text() == "content"


def test_delete_file(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "to_delete.txt").write_text("bye")
    result = fs.delete_file(tmp_path / "to_delete.txt")
    assert result["deleted"] is True
    assert not (tmp_path / "to_delete.txt").exists()


def test_delete_file_not_found(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    result = fs.delete_file(tmp_path / "missing.txt")
    assert "error" in result


def test_get_metadata(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    (tmp_path / "file.txt").write_text("content")
    result = fs.get_metadata(tmp_path / "file.txt")
    assert result["type"] == "file"
    assert result["exists"] is True


def test_path_traversal_blocked(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    with pytest.raises(PathValidationError):
        fs.validate_path(tmp_path / ".." / ".." / "secret.txt")


def test_access_denied_outside_roots(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    other = tmp_path.parent / "other"
    other.mkdir(exist_ok=True)
    with pytest.raises(AccessDeniedError):
        fs.require_access(other / "file.txt")


def test_get_risk_level():
    fs = FilesystemTool()
    assert fs.get_risk_level("read") == RiskLevel.READ
    assert fs.get_risk_level("create") == RiskLevel.MEDIUM
    assert fs.get_risk_level("delete") == RiskLevel.HIGH


def test_allowed_roots_property(tmp_path):
    fs = FilesystemTool(allowed_roots=[tmp_path])
    assert tmp_path.resolve() in fs.allowed_roots


def test_workspace_property(tmp_path):
    fs = FilesystemTool(workspace=tmp_path)
    assert fs.workspace == tmp_path
