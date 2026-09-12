"""Backend process lifecycle management.

Handles starting, stopping, health-checking, and crash recovery
for the ULTRON Python backend server.
"""

from __future__ import annotations

import http.client
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("jarvis.desktop.process")


def _find_backend_executable() -> Optional[Path]:
    """Find the backend executable (PyInstaller bundle or dev Python)."""
    # If running as PyInstaller bundle
    if getattr(sys, "frozen", False):
        # In a PyInstaller bundle, the backend is bundled as a separate exe
        # or embedded in the same exe
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        backend_exe = bundle_dir / "ultron_backend.exe"
        if backend_exe.exists():
            return backend_exe
        # Fallback: look for the Python backend script
        backend_script = bundle_dir / "ultron_backend.py"
        if backend_script.exists():
            return backend_script
        return None

    # Development mode: find the project root and use Python directly
    project_root = Path(__file__).resolve().parent.parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python

    # Fallback to system Python
    return Path(sys.executable)


def _find_project_root() -> Path:
    """Find the project root directory."""
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        return bundle_dir
    return Path(__file__).resolve().parent.parent


def _is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
            return False  # Port is in use
    except (ConnectionRefusedError, OSError):
        return True  # Port is available


def _find_available_port(preferred: int = 8080, host: str = "127.0.0.1") -> int:
    """Find an available port, starting with the preferred port."""
    if _is_port_available(preferred, host):
        return preferred
    for port in range(8081, 8100):
        if _is_port_available(port, host):
            return port
    raise RuntimeError(f"No available port found in range 8080-8099")


class BackendProcess:
    """Manages the ULTRON backend process lifecycle."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        start_timeout: int = 30,
        on_status_change: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.start_timeout = start_timeout
        self.on_status_change = on_status_change

        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._running = False
        self._status = "stopped"
        self._lock = threading.Lock()
        self._restart_count = 0
        self._max_restarts = 3
        self._last_crash_time = 0.0

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None and self._process.poll() is None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _set_status(self, status: str) -> None:
        with self._lock:
            self._status = status
        if self.on_status_change:
            try:
                self.on_status_change(status)
            except Exception:
                pass

    def start(self) -> bool:
        """Start the backend server."""
        with self._lock:
            if self._running:
                logger.warning("Backend already running")
                return True

        # Find available port
        try:
            self.port = _find_available_port(self.port, self.host)
        except RuntimeError as e:
            logger.error(f"Cannot find available port: {e}")
            self._set_status("error")
            return False

        self._set_status("starting")
        self._running = True
        self._restart_count = 0

        # Start the backend process
        try:
            self._start_process()
        except Exception as e:
            logger.error(f"Failed to start backend: {e}")
            self._set_status("error")
            self._running = False
            return False

        # Start health check thread
        self._health_thread = threading.Thread(
            target=self._health_check_loop, daemon=True, name="jarvis-health"
        )
        self._health_thread.start()

        return True

    def _start_process(self) -> None:
        """Start the backend subprocess."""
        project_root = _find_project_root()
        backend_exe = _find_backend_executable()

        if backend_exe is None:
            raise RuntimeError("Cannot find backend executable")

        # Build command
        if getattr(sys, "frozen", False):
            # PyInstaller bundle mode
            if backend_exe.suffix == ".exe":
                cmd = [str(backend_exe)]
            else:
                cmd = [str(backend_exe), "-m", "ultron", "--web", "--headless",
                       "--port", str(self.port), "--host", self.host]
        else:
            # Development mode
            cmd = [str(backend_exe), "-m", "ultron", "--web", "--headless",
                   "--port", str(self.port), "--host", self.host]

        # Set environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root)
        env["ULTRON_HOST"] = self.host
        env["ULTRON_PORT"] = str(self.port)

        logger.info(f"Starting backend: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        logger.info(f"Backend started with PID: {self._process.pid}")

    def _health_check_loop(self) -> None:
        """Background thread that monitors backend health."""
        consecutive_failures = 0

        while self._running:
            time.sleep(3)

            if not self._running:
                break

            # Check if process is still alive
            if self._process and self._process.poll() is not None:
                exit_code = self._process.returncode
                logger.error(f"Backend process exited with code: {exit_code}")
                self._set_status("crashed")

                # Attempt restart
                if self._restart_count < self._max_restarts:
                    self._restart_count += 1
                    logger.info(f"Attempting restart ({self._restart_count}/{self._max_restarts})")
                    time.sleep(2)
                    try:
                        self._start_process()
                        consecutive_failures = 0
                        continue
                    except Exception as e:
                        logger.error(f"Restart failed: {e}")
                else:
                    logger.error("Max restarts reached")
                    self._running = False
                    self._set_status("failed")
                break

            # HTTP health check
            try:
                conn = http.client.HTTPConnection(self.host, self.port, timeout=5)
                conn.request("GET", "/api/status")
                response = conn.getresponse()
                conn.close()

                if response.status == 200:
                    consecutive_failures = 0
                    if self._status != "running":
                        self._set_status("running")
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 5:
                        logger.warning(f"Backend health check failed ({consecutive_failures} consecutive)")
            except Exception:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    logger.warning(f"Backend unreachable ({consecutive_failures} consecutive)")

    def stop(self) -> None:
        """Stop the backend server gracefully."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        self._set_status("stopping")

        if self._process:
            try:
                # Try graceful shutdown first
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    self._process.kill()
                    self._process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Error stopping backend: {e}")

        self._set_status("stopped")
        logger.info("Backend stopped")

    def restart(self) -> bool:
        """Restart the backend server."""
        self.stop()
        time.sleep(1)
        return self.start()

    def get_status_info(self) -> dict:
        """Get detailed backend status information."""
        return {
            "status": self._status,
            "pid": self._process.pid if self._process else None,
            "port": self.port,
            "host": self.host,
            "url": self.url,
            "restart_count": self._restart_count,
            "is_running": self.is_running,
        }
