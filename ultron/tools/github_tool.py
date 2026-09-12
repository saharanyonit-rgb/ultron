"""GitHub integration tools — search, clone, create repositories, push, pull.

Local operations use the installed `git` CLI (same convention as git_tool.py);
remote API operations use httpx against api.github.com. Authentication is read
from the GITHUB_TOKEN / GH_TOKEN environment variable. The token is never
included in tool output and is never written into a git remote URL.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ultron.tools.base import Tool

API_BASE = "https://api.github.com"


def _env_token() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")


def _api(method: str, path: str, token: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call the GitHub REST API. Returns (status_code, payload) as a dict."""
    try:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(timeout=25, follow_redirects=True) as client:
            response = client.request(method, API_BASE + path, headers=headers, json=json)
        try:
            payload = response.json()
        except Exception:
            payload = {"message": response.text[:300]} if response.text else {}
        return {
            "status_code": response.status_code,
            "data": payload,
            "success": 200 <= response.status_code < 300,
        }
    except httpx.RequestError as exc:
        return {"status_code": 0, "data": {}, "success": False, "error": f"GitHub API unreachable: {exc}"}
    except Exception as exc:
        return {"status_code": 0, "data": {}, "success": False, "error": f"GitHub API error: {exc}"}


def _git(cwd: str, *args: str, timeout: int = 120) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "Git is not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Git command timed out after {timeout}s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _normalize_repo(repo: str) -> str:
    repo = repo.strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:"):
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
    return repo.rstrip("/")


class GitHubSearchTool(Tool):
    name = "github_search"
    description = (
        "Search GitHub for public repositories matching a query. "
        "Returns the top repositories with stars, language, description, and clone URL. "
        "Use when the user asks to find repos on GitHub, search GitHub, or wants code/links for a topic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords, e.g. 'ai chatbot' or 'torch resnet'.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 8, max 30).",
            },
            "token": {
                "type": "string",
                "description": "Optional GitHub token (otherwise read from GITHUB_TOKEN env).",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "repositories": {"type": "array"},
            "total": {"type": "integer"},
            "error": {"type": "string"},
        },
    }

    def run(self, query: str, limit: int = 8, token: str = "", **_: Any) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"success": False, "error": "Missing 'query' parameter."}
        token = token or _env_token()

        result = _api("GET", f"/search/repositories?q={quote(query)}&per_page={min(max(int(limit), 1), 30)}", token)
        if not result.get("success", False):
            code = result.get("status_code", 0)
            msg = result.get("data", {}).get("message", "Search failed") if isinstance(result.get("data"), dict) else "Search failed"
            return {"success": False, "error": f"GitHub API error ({code}): {msg}", "repositories": [], "total": 0}

        items = result["data"].get("items", []) if isinstance(result.get("data"), dict) else []
        repos = [
            {
                "full_name": it.get("full_name", ""),
                "owner": (it.get("owner") or {}).get("login", ""),
                "description": it.get("description"),
                "stars": it.get("stargazers_count", 0),
                "forks": it.get("forks_count", 0),
                "language": it.get("language"),
                "html_url": it.get("html_url", ""),
                "clone_url": it.get("clone_url", ""),
                "updated_at": it.get("updated_at", ""),
            }
            for it in items
        ]
        return {"success": True, "repositories": repos, "total": len(repos)}


class GitHubCloneTool(Tool):
    name = "github_clone"
    description = (
        "Clone (download) a GitHub repository to local disk. "
        "Accept an 'owner/repo' name or a full URL. Optionally specify a target directory."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "'owner/repo' or a full GitHub URL, e.g. 'torch/my-auto-driver'.",
            },
            "target_dir": {
                "type": "string",
                "description": "Directory to clone into (default: current working directory).",
            },
            "depth": {
                "type": "integer",
                "description": "Shallow clone history depth (1 for a quick copy, 0 for full history).",
            },
        },
        "required": ["repo"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "output_file": {"type": "string"},
            "repo": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, repo: str, target_dir: str = "", depth: int = 1, **_: Any) -> Dict[str, Any]:
        repo = _normalize_repo(repo)
        if not repo or "/" not in repo:
            return {"success": False, "error": "Provide a repository as 'owner/repo' or a full GitHub URL."}

        base = Path(target_dir).expanduser() if target_dir else Path.cwd()
        base.mkdir(parents=True, exist_ok=True)
        dest = base / repo.split("/")[-1]

        args = ["clone"]
        if depth and int(depth) > 0:
            args += ["--depth", str(int(depth))]
        args += [f"https://github.com/{repo}.git", str(dest)]

        result = _git(str(base), *args)
        if result.get("return_code", 1) != 0:
            return {"success": False, "error": result.get("stderr") or result.get("stdout") or "Clone failed"}
        return {"success": True, "output_file": str(dest), "repo": repo}


class GitHubCreateRepoTool(Tool):
    name = "github_create_repo"
    description = (
        "Create a new repository on GitHub, optionally pushing an existing local folder to it. "
        "Requires a GITHUB_TOKEN environment variable (or pass 'token'). "
        "If a local folder is provided it becomes the repo and is pushed as the initial commit."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "New repository name.",
            },
            "local_dir": {
                "type": "string",
                "description": "Optional local folder whose contents become the repository and are pushed.",
            },
            "description": {
                "type": "string",
                "description": "Short description of the repository.",
            },
            "private": {
                "type": "boolean",
                "description": "Create as a private repository (default true).",
            },
            "token": {
                "type": "string",
                "description": "Optional GitHub token (otherwise read from GITHUB_TOKEN env).",
            },
        },
        "required": ["name"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "html_url": {"type": "string"},
            "clone_url": {"type": "string"},
            "pushed": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        name: str,
        local_dir: str = "",
        description: str = "",
        private: bool = True,
        token: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            return {"success": False, "error": "Missing 'name' parameter."}
        token = token or _env_token()
        if not token:
            return {
                "success": False,
                "error": "No GitHub token found. Set GITHUB_TOKEN (or GH_TOKEN) in the environment / .env file.",
            }

        result = _api(
            "POST",
            "/user/repos",
            token,
            json={
                "name": name,
                "description": description or "",
                "private": bool(private),
            },
        )
        if not result.get("success", False):
            code = result.get("status_code", 0)
            msg = result.get("data", {}).get("message", "Could not create repository") if isinstance(result.get("data"), dict) else "Could not create repository"
            return {"success": False, "error": f"GitHub API error ({code}): {msg}"}

        html_url = result["data"].get("html_url", "")
        clone_url = result["data"].get("clone_url", "")

        pushed = False
        if local_dir:
            pushed = self._push_local(local_dir, clone_url)

        return {"success": True, "html_url": html_url, "clone_url": clone_url, "pushed": pushed}

    @staticmethod
    def _push_local(local_dir: str, clone_url: str) -> bool:
        path = Path(local_dir).expanduser()
        if not path.is_dir():
            return False

        git_ready = _git(str(path), "rev-parse", "--is-inside-work-tree")
        if git_ready.get("return_code", 1) != 0:
            _git(str(path), "init")

        _git(str(path), "add", "-A")
        head_check = _git(str(path), "rev-parse", "--verify", "--quiet", "HEAD")
        if head_check.get("return_code", 1) != 0:
            _git(str(path), "commit", "-m", "Initial commit from JARVIS")

        head = _git(str(path), "branch", "--show-current").get("stdout", "").strip()
        if not head:
            head = "main"

        _git(str(path), "remote", "remove", "origin")
        _git(str(path), "remote", "add", "origin", clone_url)
        push = _git(str(path), "push", "-u", "origin", head)
        return push.get("return_code", 1) == 0


class GitHubPushTool(Tool):
    name = "github_push"
    description = (
        "Push local commits in a repository to its remote (origin) on GitHub. "
        "Git authentication uses your configured git credentials / credential manager."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the local git repository.",
            },
            "remote": {
                "type": "string",
                "description": "Remote name (default 'origin').",
            },
            "branch": {
                "type": "string",
                "description": "Branch to push (default: current branch).",
            },
            "force": {
                "type": "boolean",
                "description": "Allow force push (default false).",
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "pushed": {"type": "boolean"},
            "stdout": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, repo_path: str, remote: str = "origin", branch: str = "", force: bool = False, **_: Any) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.is_dir():
            return {"success": False, "error": f"Path not found: {path}"}

        branch = branch or _git(str(path), "branch", "--show-current").get("stdout", "").strip()
        if not branch:
            return {"success": False, "error": "Could not determine current branch."}

        args = ["push"]
        if force:
            args += ["--force-with-lease"]
        args += [remote, branch]

        result = _git(str(path), *args)
        if result.get("return_code", 1) != 0:
            return {"success": False, "pushed": False, "error": result.get("stderr") or result.get("stdout") or "Push failed"}
        return {"success": True, "pushed": True, "stdout": result.get("stdout", "")[:400]}


class GitHubPullTool(Tool):
    name = "github_pull"
    description = (
        "Update a local git repository from its remote (origin) on GitHub "
        "using a fast-forward pull. Fails safely if local changes would conflict."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the local git repository.",
            },
            "remote": {
                "type": "string",
                "description": "Remote name (default 'origin').",
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "updated": {"type": "boolean"},
            "stdout": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, repo_path: str, remote: str = "origin", **_: Any) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.is_dir():
            return {"success": False, "error": f"Path not found: {path}"}

        result = _git(str(path), "pull", "--ff-only", remote)
        if result.get("return_code", 1) != 0:
            return {"success": False, "updated": False, "error": result.get("stderr") or result.get("stdout") or "Pull failed"}
        return {"success": True, "updated": True, "stdout": result.get("stdout", "")[:400]}


def quote(text: str) -> str:
    from urllib.parse import quote as _q

    return _q(text, safe="")


__all__ = [
    "GitHubSearchTool",
    "GitHubCloneTool",
    "GitHubCreateRepoTool",
    "GitHubPushTool",
    "GitHubPullTool",
    "_api",
    "_git",
    "_env_token",
]