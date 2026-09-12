"""System tray integration using pystray.

Provides system tray icon with context menu for JARVIS desktop application.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("jarvis.desktop.tray")

# Lazy imports to avoid import errors when pystray is not available
_tray_icon = None
_tray_menu = None


def _import_pystray():
    """Lazy import pystray with PIL image support."""
    global _tray_icon, _tray_menu
    try:
        import pystray
        from pystray import MenuItem as item
        _tray_icon = pystray.Icon
        _tray_menu = pystray.Menu
        return pystray, item
    except ImportError:
        logger.error("pystray not installed. Install with: pip install pystray")
        return None, None


def _create_icon_image(color: str = "#3dffb0"):
    """Create a simple tray icon image."""
    try:
        from PIL import Image, ImageDraw

        # Create a 64x64 icon with a "J" letter
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw circle background
        draw.ellipse([4, 4, size - 4, size - 4], fill=(30, 30, 30, 255))

        # Draw "J" letter
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        draw.rounded_rectangle([12, 12, 52, 52], radius=8, fill=(r, g, b, 255))

        # Draw J
        draw.text((22, 14), "J", fill=(0, 0, 0, 255))

        return image
    except Exception as e:
        logger.error(f"Failed to create icon image: {e}")
        return None


class SystemTray:
    """System tray icon for JARVIS."""

    def __init__(
        self,
        on_open: Optional[Callable] = None,
        on_hide: Optional[Callable] = None,
        on_show: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
        accent_color: str = "#3dffb0",
    ):
        self.on_open = on_open
        self.on_hide = on_hide
        self.on_show = on_show
        self.on_exit = on_exit
        self.accent_color = accent_color
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> bool:
        """Start the system tray icon."""
        pystray, item = _import_pystray()
        if pystray is None:
            return False

        image = _create_icon_image(self.accent_color)
        if image is None:
            return False

        # Create menu
        menu = pystray.Menu(
            item("Open JARVIS", self._on_open, default=True),
            pystray.Menu.SEPARATOR,
            item("Show", self._on_show),
            item("Hide", self._on_hide),
            pystray.Menu.SEPARATOR,
            item("Exit", self._on_exit),
        )

        self._icon = pystray.Icon(
            "JARVIS",
            image,
            "JARVIS - Personal AI Assistant",
            menu,
        )

        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="jarvis-tray"
        )
        self._thread.start()
        logger.info("System tray started")
        return True

    def _run(self) -> None:
        """Run the tray icon (blocking)."""
        try:
            if self._icon:
                self._icon.run()
        except Exception as e:
            logger.error(f"Tray icon error: {e}")

    def stop(self) -> None:
        """Stop the system tray icon."""
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        logger.info("System tray stopped")

    def update_tooltip(self, tooltip: str) -> None:
        """Update the tray icon tooltip."""
        if self._icon:
            try:
                self._icon.title = tooltip
            except Exception:
                pass

    def update_icon(self, color: str) -> None:
        """Update the tray icon color."""
        if self._icon:
            try:
                image = _create_icon_image(color)
                if image:
                    self._icon.icon = image
            except Exception:
                pass

    def show_notification(self, title: str, message: str) -> None:
        """Show a notification balloon from the tray icon."""
        if self._icon:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _on_open(self, icon=None, item=None) -> None:
        if self.on_open:
            self.on_open()

    def _on_show(self, icon=None, item=None) -> None:
        if self.on_show:
            self.on_show()

    def _on_hide(self, icon=None, item=None) -> None:
        if self.on_hide:
            self.on_hide()

    def _on_exit(self, icon=None, item=None) -> None:
        if self.on_exit:
            self.on_exit()
