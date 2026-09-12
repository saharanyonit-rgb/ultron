"""Windows notification integration.

Uses win10toast or plyer for native Windows notifications.
Falls back to tray balloon notifications.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

logger = logging.getLogger("jarvis.desktop.notifications")


class NotificationManager:
    """Manages Windows desktop notifications."""

    def __init__(self, app_name: str = "JARVIS"):
        self.app_name = app_name
        self._toast = None
        self._available = False
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize the notification backend."""
        if sys.platform != "win32":
            logger.info("Notifications not available on non-Windows platform")
            return

        # Try win10toast first
        try:
            from win10toast import ToastNotifier
            self._toast = ToastNotifier()
            self._available = True
            logger.info("Using win10toast for notifications")
            return
        except ImportError:
            pass

        # Try winotify (Windows 10/11 toast notifications)
        try:
            from winotify import Notification, audio
            self._toast = "winotify"
            self._available = True
            logger.info("Using winotify for notifications")
            return
        except ImportError:
            pass

        logger.info("No notification backend available (install win10toast or winotify)")

    def notify(
        self,
        title: str,
        message: str,
        duration: int = 5,
        icon_path: Optional[str] = None,
    ) -> bool:
        """Show a Windows notification."""
        if not self._available:
            return False

        try:
            if self._toast == "winotify":
                return self._notify_winotify(title, message, icon_path)
            elif self._toast is not None:
                return self._notify_win10toast(title, message, duration, icon_path)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            return False

        return False

    def _notify_winotify(
        self, title: str, message: str, icon_path: Optional[str]
    ) -> bool:
        """Show notification using winotify."""
        from winotify import Notification

        toast = Notification(
            app_id=self.app_name,
            title=title,
            msg=message,
            icon=icon_path or "",
        )
        toast.show()
        return True

    def _notify_win10toast(
        self, title: str, message: str, duration: int, icon_path: Optional[str]
    ) -> bool:
        """Show notification using win10toast."""
        self._toast.show_toast(
            title=title,
            msg=message,
            duration=duration,
            threaded=True,
            icon_path=icon_path,
        )
        return True
