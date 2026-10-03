"""Native desktop window host for the JARVIS user interface.

Replaces the "launch the default browser at http://127.0.0.1:PORT" flow with a
real operating-system window, so JARVIS no longer depends on Chrome (or any
other browser) being installed.

On Windows this uses pywebview's EdgeChromium backend, which drives the
WebView2 runtime that ships as part of Windows 10 21H2+ and Windows 11. The
frontend is not modified or re-hosted in any way: the window simply loads the
same URL from the in-process backend, so the REST API, the SSE event stream
and the three.js orb behave exactly as they do in a browser.

Threading
---------
`webview.start()` must be called from the main thread. The WinForms backend
immediately hands the GUI loop to its own STA thread and leaves the main
thread polling it, so the caller stays responsive to signals and to
`threading.Event`s. Control methods (`show`, `hide`, `close`, ...) are
marshalled onto the UI thread by pywebview itself, which makes them safe to
call from the pystray thread.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from desktop.config import DesktopConfig, get_app_data_dir

logger = logging.getLogger("jarvis.desktop.window")

WINDOW_TITLE = "JARVIS - Personal AI Assistant"

# Matches the frontend's page background so there is no white flash while the
# first frame renders.
WINDOW_BACKGROUND = "#05070A"

MIN_WIDTH = 900
MIN_HEIGHT = 600

# WebView2 registers its runtime under this EdgeUpdate client GUID.
_WEBVIEW2_CLIENT_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
_WEBVIEW2_REG_PATHS = (
    rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}",
    rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WEBVIEW2_CLIENT_GUID}",
)
_WEBVIEW2_EXE = "msedgewebview2.exe"


def _version_key(name: str) -> tuple[int, ...]:
    """Sortable key for a dotted version directory name."""
    parts = []
    for chunk in name.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _webview2_version_from_registry() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for path in _WEBVIEW2_REG_PATHS:
            try:
                with winreg.OpenKey(root, path) as key:
                    version, _ = winreg.QueryValueEx(key, "pv")
            except OSError:
                continue
            if version:
                return str(version)
    return None


def _webview2_version_from_disk() -> str | None:
    """Fallback probe for machines where the EdgeUpdate key is not readable."""
    bases = (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "EdgeWebView"
        / "Application",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Microsoft"
        / "EdgeWebView"
        / "Application",
    )
    for base in bases:
        try:
            candidates = sorted(base.iterdir(), key=lambda p: _version_key(p.name), reverse=True)
        except OSError:
            continue
        for candidate in candidates:
            if (candidate / _WEBVIEW2_EXE).exists():
                return candidate.name
    return None


def webview2_version() -> str | None:
    """Return the installed WebView2 runtime version, or None if absent."""
    return _webview2_version_from_registry() or _webview2_version_from_disk()


def probe(backend: str = "auto") -> tuple[bool, str]:
    """Check whether an embedded window can be hosted.

    Returns ``(available, reason)``. ``reason`` is safe to log or show in the
    tray tooltip, and explains either why the window works or why it cannot.
    """
    try:
        import webview  # noqa: F401
    except Exception as exc:  # pragma: no cover - depends on install state
        return False, f"pywebview unavailable ({exc.__class__.__name__})"

    if sys.platform != "win32":
        return True, f"pywebview on {sys.platform}"

    version = webview2_version()
    if version is None:
        return False, "WebView2 runtime not installed"
    if backend not in ("auto", "edgechromium"):
        return True, f"pywebview backend {backend} (WebView2 {version} present)"

    edge_version = _edge_version()
    detail = f" (Edge {edge_version})" if edge_version else ""
    return True, f"WebView2 {version}{detail}"


def _edge_version() -> str | None:
    """Version of the Edge browser proper, which is what WebView2 mirrors."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for path in (
            r"SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon",
            r"SOFTWARE\Microsoft\Edge\BLBeacon",
        ):
            try:
                with winreg.OpenKey(root, path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
            except OSError:
                continue
            if version:
                return str(version)
    return None


class NativeWindow:
    """The JARVIS UI, hosted in a WebView2 window."""

    def __init__(
        self,
        url: str,
        config: DesktopConfig | None = None,
        *,
        backend: str = "auto",
        hidden: bool = False,
        on_closed: Callable[[], None] | None = None,
    ):
        self.url = url
        self.config = config or DesktopConfig()
        self.backend = backend
        self.hidden = hidden
        self.on_closed = on_closed

        self._window: Any = None
        self._lock = threading.Lock()
        self._allow_close = threading.Event()
        self._renderer: str | None = None
        self._closed = False
        self._hidden_for_tray = bool(hidden)

    # -- lifecycle -----------------------------------------------------

    @property
    def renderer(self) -> str | None:
        """Backend pywebview actually bound to, e.g. ``edgechromium``."""
        return self._renderer

    @property
    def closed(self) -> bool:
        return self._closed

    def run(self) -> None:
        """Create the window and pump the GUI loop. Blocks until it closes."""
        import webview

        with self._lock:
            self._window = webview.create_window(
                WINDOW_TITLE,
                url=self.url,
                width=self.config.window_width,
                height=self.config.window_height,
                x=self.config.window_x,
                y=self.config.window_y,
                min_size=(MIN_WIDTH, MIN_HEIGHT),
                maximized=self.config.window_maximized,
                hidden=self.hidden,
                frameless=False,
                easy_drag=False,
                background_color=WINDOW_BACKGROUND,
                confirm_close=False,
                on_top=False,
                text_select=True,
            )
            self._window.events.closing += self._on_closing
            self._window.events.loaded += self._on_loaded
            self._window.events.closed += self._on_closed

        logger.info(
            "Hosting %s in a native window (%s)",
            self.url,
            self.backend if self.backend != "auto" else "auto",
        )

        storage = get_app_data_dir() / "webview"
        try:
            webview.start(
                gui=cast(Any, None if self.backend == "auto" else self.backend),
                private_mode=False,
                storage_path=str(storage),
            )
        except Exception as exc:
            logger.error("Native window failed: %s", exc, exc_info=True)
            raise
        finally:
            self._closed = True

        logger.info("Native window closed (renderer=%s)", self._renderer)
        if self.on_closed:
            self.on_closed()

    # -- window control (safe from any thread) -------------------------

    def show(self) -> bool:
        """Bring the window to the front, un-minimizing it if needed."""
        with self._lock:
            window = self._window
            if window is None or self._closed:
                logger.debug("Window show ignored: no window")
                return False
            try:
                # pywebview's show() does not un-minimize, so restore first.
                window.restore()
                window.show()
            except Exception as exc:
                logger.warning("Could not show window: %s", exc)
                return False
            self._hidden_for_tray = False
            logger.debug("Window show ok")
            return True

    def hide(self) -> bool:
        """Hide the window without tearing down the web view."""
        if self._dispatch("hide"):
            self._hidden_for_tray = True
            return True
        return False

    def toggle(self) -> bool:
        """Show the window if hidden, otherwise hide it."""
        with self._lock:
            if self._window is None or self._closed:
                return False
            was_visible = self._is_visible()
        # Dispatch outside the lock: hide/show take it again, and Lock is not
        # reentrant.
        return self.hide() if was_visible else self.show()

    def close(self) -> bool:
        """Close the window for real, bypassing close-to-tray."""
        self._allow_close.set()
        return self._dispatch("destroy")

    def _dispatch(self, method: str, **kwargs) -> bool:
        with self._lock:
            window = self._window
            if window is None or self._closed:
                logger.debug("Window command %s ignored: no window", method)
                return False
            try:
                getattr(window, method)(**kwargs)
            except Exception as exc:
                logger.warning("Window command %s failed: %s", method, exc)
                return False
            logger.debug("Window command %s ok", method)
            return True

    def _is_visible(self) -> bool:
        """Best-effort visibility probe used to make ``toggle`` idempotent.

        WinForms does not expose a cross-thread ``Visible`` read that pywebview
        surfaces, so this tracks the two states we ourselves drive: the window
        was created hidden, or it was hidden to the tray by ``_on_closing``.
        """
        window = self._window
        if window is None or self._closed:
            return False
        return not self._hidden_for_tray

    # -- pywebview events ----------------------------------------------

    def _on_loaded(self) -> None:
        try:
            import webview

            self._renderer = webview.renderer
        except Exception:
            self._renderer = None
        logger.info("Native window loaded (renderer=%s)", self._renderer)

    def _on_closing(self) -> bool | None:
        """Veto the close when the app is configured to live in the tray.

        Returning ``False`` cancels pywebview's close. The ``closing`` event is
        dispatched synchronously, so the veto is honoured before WinForms acts
        on it.
        """
        if self._allow_close.is_set() or not self.config.close_to_tray:
            self._capture_geometry()
            return None
        self._capture_geometry()
        self._hidden_for_tray = True
        self.hide()
        logger.info("Window close intercepted; hidden to tray")
        return False

    def _on_closed(self) -> None:
        self._closed = True
        logger.info("Window closed")

    def _capture_geometry(self) -> None:
        """Persist window size/position so the next launch restores it."""
        window = self._window
        if window is None:
            return
        try:
            width = int(window.width)
            height = int(window.height)
            if width <= MIN_WIDTH or height <= MIN_HEIGHT:
                return  # minimized, or a bogus geometry mid-transition
            self.config.window_width = width
            self.config.window_height = height
            self.config.window_x = int(window.x)
            self.config.window_y = int(window.y)
            self.config.window_maximized = bool(window.maximized)
        except Exception as exc:
            logger.debug("Could not capture window geometry: %s", exc)


__all__ = ["NativeWindow", "WINDOW_TITLE", "probe", "webview2_version"]
