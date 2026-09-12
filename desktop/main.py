"""JARVIS Desktop Application - Main Entry Point.

This is the primary entry point for the JARVIS desktop application.
It starts the ULTRON backend in-process, manages the system tray,
and provides a native Windows desktop experience.

Usage:
    python -m desktop              # Start JARVIS desktop
    python -m desktop --no-tray    # Start without system tray
    python -m desktop --port 8080  # Specify backend port
"""

from __future__ import annotations

import argparse
import ctypes
import http.client
import logging
import os
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path

from desktop.config import DesktopConfig, get_logs_dir, get_app_data_dir
from desktop.server import InProcessBackend
from desktop.tray import SystemTray
from desktop.notifications import NotificationManager

logger = logging.getLogger("jarvis.desktop")

# Application metadata
APP_NAME = "JARVIS"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Personal AI Desktop Assistant"


class JarvisDesktop:
    """Main JARVIS Desktop application."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.config = DesktopConfig.load()
        self.backend: InProcessBackend = None  # type: ignore[assignment]
        self.tray: SystemTray = None  # type: ignore[assignment]
        self.notifications: NotificationManager = None  # type: ignore[assignment]
        self._shutdown_event = threading.Event()
        self._mutex = None

    def run(self) -> int:
        """Run the JARVIS desktop application."""
        # Setup logging
        self._setup_logging()

        logger.info(f"JARVIS Desktop v{APP_VERSION} starting...")

        # Check for single instance
        if not self._acquire_instance_lock():
            logger.info("Another JARVIS instance is already running")
            self._focus_existing_instance()
            return 0

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # Start backend
            self._start_backend()

            # Start system tray
            if not self.args.no_tray:
                self._start_tray()

            # Open browser UI
            if not self.args.no_browser and not self.args.start_minimized:
                self._open_browser()

            # Send startup notification
            if self.config.show_notifications and self.notifications:
                self.notifications.notify(
                    "JARVIS Online",
                    "Personal AI Assistant is ready",
                    duration=3,
                )

            # Show startup info
            self._print_startup_info()

            # Wait for shutdown
            self._wait_for_shutdown()

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            return 1
        finally:
            self._shutdown()

        return 0

    def _setup_logging(self) -> None:
        """Configure logging for the desktop application."""
        logs_dir = get_logs_dir()
        log_file = logs_dir / "jarvis_desktop.log"

        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.args.debug else logging.INFO)

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if self.args.debug else logging.INFO)
        console.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
        ))
        root_logger.addHandler(console)

        # File handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(file_handler)

        logger.info(f"Logging to: {log_file}")

    def _acquire_instance_lock(self) -> bool:
        """Ensure only one instance of JARVIS is running."""
        if sys.platform != "win32":
            return True

        try:
            mutex_name = "JARVIS_Desktop_SingleInstance"
            self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                logger.info("JARVIS already running (mutex exists)")
                return False
            return True
        except Exception as e:
            logger.warning(f"Could not create mutex: {e}")
            return True

    def _focus_existing_instance(self) -> None:
        """Focus an existing JARVIS window."""
        if sys.platform != "win32":
            return

        try:
            import ctypes.wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "JARVIS - Personal AI Assistant")
            if hwnd:
                user32.SetForegroundWindow(hwnd)
                logger.info("Focused existing JARVIS window")
        except Exception as e:
            logger.debug(f"Could not focus existing window: {e}")

    def _start_backend(self) -> None:
        """Start the ULTRON backend server in-process."""
        port = self.args.port or self.config.backend_port
        host = self.args.host or self.config.backend_host

        # Set environment for the backend
        os.environ.setdefault("JARVIS_HOST", host)
        os.environ.setdefault("JARVIS_PORT", str(port))

        self.backend = InProcessBackend(host=host, port=port)
        self.notifications = NotificationManager(APP_NAME)

        if not self.backend.start():
            raise RuntimeError("Failed to start ULTRON backend")

        logger.info(f"Backend running at {self.backend.url}")
        self._wait_for_backend_ready()

    def _wait_for_backend_ready(self, timeout: int = 30) -> bool:
        """Wait for the backend to respond to health checks."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                conn = http.client.HTTPConnection(self.backend.host, self.backend.port, timeout=2)
                conn.request("GET", "/api/status")
                response = conn.getresponse()
                conn.close()
                if response.status == 200:
                    logger.info("Backend ready")
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        logger.warning("Backend health check timed out")
        return False

    def _start_tray(self) -> None:
        """Start the system tray icon."""
        self.tray = SystemTray(
            on_open=self._on_tray_open,
            on_hide=self._on_tray_hide,
            on_show=self._on_tray_show,
            on_exit=self._on_tray_exit,
            accent_color=self.config.accent_color,
        )

        if not self.tray.start():
            logger.warning("Failed to start system tray (pystray not available)")

    def _on_tray_open(self) -> None:
        """Handle tray 'Open' click."""
        self._open_browser()

    def _on_tray_show(self) -> None:
        """Handle tray 'Show' click."""
        self._open_browser()

    def _on_tray_hide(self) -> None:
        """Handle tray 'Hide' click."""
        logger.info("Hide requested")

    def _on_tray_exit(self) -> None:
        """Handle tray 'Exit' click."""
        logger.info("Exit requested from tray")
        self._shutdown_event.set()

    def _open_browser(self) -> None:
        """Open the JARVIS web UI in the default browser."""
        if self.backend and self.backend.is_running:
            url = self.backend.url
            logger.info(f"Opening browser: {url}")
            threading.Thread(
                target=webbrowser.open,
                args=(url,),
                daemon=True,
            ).start()
        else:
            logger.warning("Backend not running, cannot open browser")

    def _print_startup_info(self) -> None:
        """Print startup information."""
        print()
        print("=" * 60)
        print(f"  JARVIS v{APP_VERSION} - Personal AI Desktop Assistant")
        print("=" * 60)
        print()
        print(f"  Backend:  {self.backend.url}")
        print(f"  Status:   Running")
        print(f"  Logs:     {get_logs_dir()}")
        print(f"  Config:   {get_app_data_dir()}")
        print()
        print("  Press Ctrl+C to exit")
        print("  System tray icon is active")
        print()
        print("=" * 60)
        print()

    def _wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        self._shutdown_event.wait()

    def _shutdown(self) -> None:
        """Clean shutdown of all components."""
        logger.info("Shutting down JARVIS...")

        # Stop tray
        if self.tray:
            self.tray.stop()

        # Stop backend
        if self.backend:
            self.backend.stop()

        # Release mutex
        if self._mutex and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.ReleaseMutex(self._mutex)
            except Exception:
                pass

        # Save config
        try:
            self.config.save()
        except Exception as e:
            logger.warning(f"Could not save config: {e}")

        logger.info("JARVIS shutdown complete")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        logger.info(f"Received signal {signum}")
        self._shutdown_event.set()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - {APP_DESCRIPTION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=int, default=0,
        help="Backend port (default: auto-detect)",
    )
    parser.add_argument(
        "--host", type=str, default=None,
        help="Backend host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-tray", action="store_true",
        help="Disable system tray icon",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't automatically open browser",
    )
    parser.add_argument(
        "--start-minimized", action="store_true",
        help="Start minimized to tray",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    app = JarvisDesktop(args)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())