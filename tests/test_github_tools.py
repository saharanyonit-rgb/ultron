"""Tests for the GitHub integration tools (API + git operations mocked, no network)."""

from __future__ import annotations

import pytest

from ultron.tools import ALL_TOOLS, ToolRegistry
from ultron.tools.github_tool import (
    GitHubCloneTool,
    GitHubCreateRepoTool,
    GitHubPullTool,
    GitHubPushTool,
    GitHubSearchTool,
    _api,
    _env_token,
    _git,
    _normalize_repo,
)


SEARCH_ITEMS = {
    "success": True,
    "status_code": 200,
    "data": {
        "items": [
            {
                "full_name": "acme/awesome-tool",
                "owner": {"login": "acme"},
                "description": "An awesome tool",
                "stargazers_count": 1234,
                "forks_count": 88,
                "language": "Python",
                "html_url": "https://github.com/acme/awesome-tool",
                "clone_url": "https://github.com/acme/awesome-tool.git",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        ]
    },
}


def test_normalize_repo():
    assert _normalize_repo("https://github.com/a/b.git") == "a/b"
    assert _normalize_repo("git@github.com:a/b.git") == "a/b"
    assert _normalize_repo("a/b") == "a/b"


def test_env_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_123")
    assert _env_token() == "ghp_test_123"
    monkeypatch.delenv("GITHUB_TOKEN")
    monkeypatch.setenv("GH_TOKEN", "ghp_alt")
    assert _env_token() == "ghp_alt"


def test_search_success(monkeypatch):
    monkeypatch.setattr("ultron.tools.github_tool._api", lambda method, path, token, json=None: SEARCH_ITEMS)
    result = GitHubSearchTool().run("awesome tool")
    assert result["success"] is True
    assert result["total"] == 1
    repo = result["repositories"][0]
    assert repo["full_name"] == "acme/awesome-tool"
    assert repo["stars"] == 1234
    assert repo["clone_url"].startswith("https://github.com/")


def test_search_missing_query():
    result = GitHubSearchTool().run("")
    assert result["success"] is False


def test_search_api_error(monkeypatch):
    def boom(method, path, token, json=None):
        return {"success": False, "status_code": 403, "data": {"message": "rate limited"}}

    monkeypatch.setattr("ultron.tools.github_tool._api", boom)
    result = GitHubSearchTool().run("python")
    assert result["success"] is False
    assert "403" in result["error"]


def test_clone_success(monkeypatch, tmp_path):
    def fake_git(cwd, *args):
        args = list(args)
        if args[0] == "clone":
            (tmp_path / "awesome-tool").mkdir(exist_ok=True)
            return {"success": True, "return_code": 0, "stdout": "Cloned", "stderr": ""}
        return {"success": True, "return_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr("ultron.tools.github_tool._git", fake_git)
    result = GitHubCloneTool().run("acme/awesome-tool", target_dir=str(tmp_path))
    assert result["success"] is True
    assert str(tmp_path / "awesome-tool") == result["output_file"]


def test_clone_invalid_repo():
    result = GitHubCloneTool().run("not-a-full-repo")
    assert result["success"] is False


def test_create_repo_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    result = GitHubCreateRepoTool().run("my-repo")
    assert result["success"] is False
    assert "token" in result["error"].lower()


def test_create_repo_success(monkeypatch):
    def fake_api(method, path, token, json=None):
        return {
            "success": True,
            "status_code": 201,
            "data": {"html_url": "https://github.com/acme/my-repo", "clone_url": "https://github.com/acme/my-repo.git"},
        }

    def fake_git(cwd, *args):
        args = list(args)
        if args[0] == "push":
            return {"success": True, "return_code": 0, "stdout": "pushed", "stderr": ""}
        if args[0] == "branch":
            return {"success": True, "return_code": 0, "stdout": "main", "stderr": ""}
        return {"success": True, "return_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr("ultron.tools.github_tool._api", fake_api)
    monkeypatch.setattr("ultron.tools.github_tool._git", fake_git)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        result = GitHubCreateRepoTool().run("my-repo", local_dir=d)
    assert result["success"] is True
    assert result["pushed"] is True
    assert "github.com/acme/my-repo" in result["html_url"]


def test_push_success(monkeypatch, tmp_path):
    def fake_git(cwd, *args):
        args = list(args)
        if args[0] == "branch":
            return {"success": True, "return_code": 0, "stdout": "main", "stderr": ""}
        if args[0] == "push":
            return {"success": True, "return_code": 0, "stdout": "Everything up-to-date", "stderr": ""}
        return {"success": True, "return_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr("ultron.tools.github_tool._git", fake_git)
    result = GitHubPushTool().run(str(tmp_path))
    assert result["success"] is True
    assert result["pushed"] is True


def test_push_failure(monkeypatch, tmp_path):
    def fake_git(cwd, *args):
        if list(args)[0] == "branch":
            return {"success": True, "return_code": 0, "stdout": "main", "stderr": ""}
        return {"success": False, "return_code": 1, "stdout": "", "stderr": "fatal: no remote"}

    monkeypatch.setattr("ultron.tools.github_tool._git", fake_git)
    result = GitHubPushTool().run(str(tmp_path))
    assert result["success"] is False


def test_pull_success(monkeypatch, tmp_path):
    def fake_git(cwd, *args):
        return {"success": True, "return_code": 0, "stdout": "Already up to date", "stderr": ""}

    monkeypatch.setattr("ultron.tools.github_tool._git", fake_git)
    result = GitHubPullTool().run(str(tmp_path))
    assert result["success"] is True
    assert result["updated"] is True


def test_github_tools_registered():
    registry = ToolRegistry(ALL_TOOLS)
    for name in ["github_search", "github_clone", "github_create_repo", "github_push", "github_pull"]:
        assert registry.exists(name), name
    assert registry.get("github_create_repo").mutates is True
    assert registry.get("github_search").mutates is False


def test_git_cli_error_handling(monkeypatch):
    def boom(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("ultron.tools.github_tool.subprocess.run", boom)
    result = _git("C:/", "status")
    assert result["success"] is False
    assert "Git is not installed" in result["error"]