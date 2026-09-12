"""Git operations tool for JARVIS pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.tools.base import Tool


def _run_git(cwd: str, *args: str, timeout: int = 120) -> Dict[str, Any]:
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
        return {"error": "Git is not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"error": f"Git command timed out after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}


class GitStatus(Tool):
    name = "git_status"
    description = "Get the current git repository status."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository root.",
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "stdout": {"type": "string"},
            "branch": {"type": "string"},
            "is_dirty": {"type": "boolean"},
            "staged": {"type": "array"},
            "unstaged": {"type": "array"},
            "untracked": {"type": "array"},
        },
    }

    def run(self, repo_path: str, **_: Any) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.exists():
            return {"error": f"Path not found: {path}"}

        status = _run_git(str(path), "status", "--porcelain")
        if "error" in status:
            return status

        branch_result = _run_git(str(path), "branch", "--show-current")
        branch = branch_result.get("stdout", "").strip()

        staged, unstaged, untracked = [], [], []
        is_dirty = False

        for line in status.get("stdout", "").split("\n"):
            if not line:
                continue
            is_dirty = True
            if len(line) < 2:
                continue
            index_status = line[0]
            worktree_status = line[1]
            file_path = line[3:].strip()

            if index_status == "?" and worktree_status == "?":
                untracked.append(file_path)
            elif index_status == "A":
                staged.append(f"+ {file_path}")
            elif worktree_status == "M":
                unstaged.append(f"~ {file_path}")
            elif index_status == "M":
                staged.append(f"* {file_path}")

        return {
            "success": True,
            "branch": branch,
            "is_dirty": is_dirty,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        }


class GitLog(Tool):
    name = "git_log"
    description = "Get the git commit history."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository root.",
            },
            "max_count": {
                "type": "integer",
                "description": "Maximum number of commits to return (default 10).",
                "default": 10,
            },
            "format": {
                "type": "string",
                "description": "Git log format string.",
                "default": "%h|%s|%an|%ad",
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "commits": {"type": "array"},
        },
    }

    def run(
        self,
        repo_path: str,
        max_count: int = 10,
        format: str = "%h|%s|%an|%ad",
        **_: Any,
    ) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.exists():
            return {"error": f"Path not found: {path}"}

        result = _run_git(
            str(path),
            "log",
            f"--max-count={max_count}",
            f"--format={format}",
        )
        if "error" in result:
            return result

        commits = []
        for line in result.get("stdout", "").split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                commits.append({
                    "hash": parts[0],
                    "subject": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                })
            elif len(parts) == 3:
                commits.append({
                    "hash": parts[0],
                    "subject": parts[1],
                    "author": parts[2],
                    "date": "",
                })

        return {"commits": commits}


class GitDiff(Tool):
    name = "git_diff"
    description = "Get the git diff for changed files."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository root.",
            },
            "file": {
                "type": "string",
                "description": "Specific file to diff (optional, diffs all by default).",
            },
            "staged": {
                "type": "boolean",
                "description": "Diff staged changes only.",
                "default": False,
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "diff": {"type": "string"},
        },
    }

    def run(
        self,
        repo_path: str,
        file: Optional[str] = None,
        staged: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.exists():
            return {"error": f"Path not found: {path}"}

        args = ["diff"]
        if staged:
            args.append("--cached")
        if file:
            args.append("--")
            args.append(file)

        result = _run_git(str(path), *args)
        return {
            "success": result.get("return_code", 1) == 0,
            "diff": result.get("stdout", ""),
            "has_changes": bool(result.get("stdout", "")),
        }


class GitBranch(Tool):
    name = "git_branch"
    description = "List, create, or delete git branches."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository root.",
            },
            "create": {
                "type": "string",
                "description": "Create a new branch with this name.",
            },
            "delete": {
                "type": "string",
                "description": "Delete a branch with this name.",
            },
        },
        "required": ["repo_path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "branches": {"type": "array"},
            "current": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        repo_path: str,
        create: Optional[str] = None,
        delete: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.exists():
            return {"error": f"Path not found: {path}"}

        if create:
            result = _run_git(str(path), "checkout", "-b", create)
            if "error" in result:
                return result
            return {"success": True, "created": create}

        if delete:
            result = _run_git(str(path), "branch", "-d", delete)
            if "error" in result:
                return result
            return {"success": result.get("return_code", 1) == 0, "deleted": delete}

        result = _run_git(str(path), "branch", "-a")
        if "error" in result:
            return result

        current_result = _run_git(str(path), "branch", "--show-current")
        current = current_result.get("stdout", "").strip()

        branches = [
            b.strip().replace("* ", "")
            for b in result.get("stdout", "").split("\n")
            if b.strip() and not b.strip().startswith("remotes/")
        ]

        return {"success": True, "branches": branches, "current": current}


class GitCommit(Tool):
    name = "git_commit"
    description = "Create a git commit with a message."
    parameters = {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the git repository root.",
            },
            "message": {
                "type": "string",
                "description": "Commit message.",
            },
            "add_all": {
                "type": "boolean",
                "description": "Stage all changed files before committing.",
                "default": True,
            },
        },
        "required": ["repo_path", "message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "commit_hash": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        repo_path: str,
        message: str,
        add_all: bool = True,
        **_: Any,
    ) -> Dict[str, Any]:
        path = Path(repo_path).expanduser()
        if not path.exists():
            return {"error": f"Path not found: {path}"}

        if add_all:
            _run_git(str(path), "add", "-A")

        result = _run_git(str(path), "commit", "-m", message)
        if "error" in result:
            return result

        if result.get("return_code", 1) != 0:
            return {"success": False, "error": result.get("stderr", "Commit failed")}

        hash_result = _run_git(str(path), "rev-parse", "--short", "HEAD")
        return {
            "success": True,
            "commit_hash": hash_result.get("stdout", "").strip(),
        }


__all__ = [
    "GitStatus",
    "GitLog",
    "GitDiff",
    "GitBranch",
    "GitCommit",
]
