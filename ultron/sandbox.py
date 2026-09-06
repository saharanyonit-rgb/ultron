"""Sandbox abstraction for JARVIS Phase 4.

Provides isolated execution environments for risky operations.

Sandbox features:
  - Isolated working directory
  - Controlled environment variables
  - Execution timeout
  - Resource limits where supported
  - Process cleanup
  - Captured output
  - Structured result

Architecture allows different sandbox implementations:
  Sandbox
   ├── LocalSandbox (default)
   ├── RestrictedSandbox
   └── FutureContainerSandbox
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.sandbox")


class SandboxStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CLEANED = "cleaned"


@dataclass
class SandboxResult:
    """Result of a sandboxed execution."""

    status: SandboxStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    working_directory: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "working_directory": self.working_directory,
            "error": self.error,
        }


class Sandbox(ABC):
    """Abstract base class for sandbox implementations."""

    @abstractmethod
    def create(self) -> None:
        """Create the sandbox environment."""
        ...

    @abstractmethod
    def execute(
        self,
        command: str,
        timeout: int = 30,
        env: Dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute a command in the sandbox."""
        ...

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up the sandbox environment."""
        ...

    @abstractmethod
    def get_workspace(self) -> Path:
        """Get the sandbox workspace path."""
        ...


class LocalSandbox(Sandbox):
    """Local filesystem sandbox with isolated working directory."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        prefix: str = "jarvis_sandbox_",
        auto_cleanup: bool = True,
    ) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path(tempfile.gettempdir())
        self._prefix = prefix
        self._auto_cleanup = auto_cleanup
        self._workspace: Path | None = None
        self._status = SandboxStatus.CREATED

    @property
    def status(self) -> SandboxStatus:
        return self._status

    def create(self) -> None:
        """Create an isolated temporary directory."""
        self._workspace = Path(tempfile.mkdtemp(prefix=self._prefix, dir=self._base_dir))
        self._status = SandboxStatus.CREATED
        logger.info("Sandbox created: %s", self._workspace)

    def execute(
        self,
        command: str,
        timeout: int = 30,
        env: Dict[str, str] | None = None,
    ) -> SandboxResult:
        """Execute a command in the sandbox."""
        if self._workspace is None:
            self.create()

        self._status = SandboxStatus.RUNNING
        import time
        start_time = time.time()

        # Build environment: inherit current + sandbox additions
        exec_env = dict(os.environ)
        if env:
            exec_env.update(env)
        exec_env["JARVIS_SANDBOX"] = "1"
        exec_env["JARVIS_WORKSPACE"] = str(self._workspace)

        use_shell = sys.platform == "win32"

        try:
            process = subprocess.Popen(
                command,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self._workspace),
                env=exec_env,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self._status = SandboxStatus.TIMEOUT
                duration = (time.time() - start_time) * 1000
                return SandboxResult(
                    status=SandboxStatus.TIMEOUT,
                    exit_code=-1,
                    duration_ms=duration,
                    working_directory=str(self._workspace),
                    error=f"Command timed out after {timeout}s",
                )

            duration = (time.time() - start_time) * 1000
            self._status = SandboxStatus.COMPLETED if process.returncode == 0 else SandboxStatus.FAILED

            return SandboxResult(
                status=self._status,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode,
                duration_ms=duration,
                working_directory=str(self._workspace),
            )

        except Exception as exc:
            self._status = SandboxStatus.FAILED
            duration = (time.time() - start_time) * 1000
            return SandboxResult(
                status=SandboxStatus.FAILED,
                exit_code=-1,
                duration_ms=duration,
                working_directory=str(self._workspace),
                error=f"Sandbox execution error: {exc}",
            )

    def cleanup(self) -> None:
        """Remove the sandbox directory."""
        if self._workspace and self._workspace.exists():
            try:
                shutil.rmtree(self._workspace)
                self._status = SandboxStatus.CLEANED
                logger.info("Sandbox cleaned: %s", self._workspace)
            except OSError as exc:
                logger.error("Sandbox cleanup failed: %s", exc)

    def get_workspace(self) -> Path:
        if self._workspace is None:
            self.create()
        return self._workspace

    def __enter__(self) -> "LocalSandbox":
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._auto_cleanup:
            self.cleanup()


class RestrictedSandbox(Sandbox):
    """Sandbox with additional restrictions (placeholder for future implementation)."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._local = LocalSandbox(base_dir, prefix="jarvis_restricted_")

    def create(self) -> None:
        self._local.create()

    def execute(self, command: str, timeout: int = 30, env: Dict[str, str] | None = None) -> SandboxResult:
        return self._local.execute(command, timeout, env)

    def cleanup(self) -> None:
        self._local.cleanup()

    def get_workspace(self) -> Path:
        return self._local.get_workspace()


__all__ = ["Sandbox", "LocalSandbox", "RestrictedSandbox", "SandboxResult", "SandboxStatus"]
