"""Mouse and Keyboard control for JARVIS — full PC automation.

Uses pyautogui for mouse/keyboard control and screen capture.
Provides:
  - Mouse: move, click, double-click, right-click, drag, scroll
  - Keyboard: type text, press hotkeys, press individual keys
  - Screen: get screen size, get mouse position, locate on screen
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.automation")

# Lazy import pyautogui to avoid import errors if not installed
_pyautogui = None


def _get_pyautogui():
    global _pyautogui
    if _pyautogui is None:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.05
            _pyautogui = pyautogui
        except ImportError:
            raise ImportError(
                "pyautogui is required for mouse/keyboard control. "
                "Install it: pip install pyautogui"
            )
    return _pyautogui


class MouseMove(Tool):
    """Move the mouse cursor to absolute screen coordinates."""

    name = "mouse_move"
    description = "Move the mouse cursor to absolute screen coordinates (x, y)."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate in pixels."},
            "y": {"type": "integer", "description": "Y coordinate in pixels."},
            "duration": {"type": "number", "description": "Time in seconds for the move. Default 0.2.", "default": 0.2},
        },
        "required": ["x", "y"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, x: int, y: int, duration: float = 0.2, **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            ag.moveTo(x, y, duration=duration)
            return {"x": x, "y": y}
        except Exception as e:
            return {"error": str(e)}


class MouseClick(Tool):
    """Click at the current mouse position or at given coordinates."""

    name = "mouse_click"
    description = "Click the mouse. Optionally at specific coordinates. Supports left, right, middle buttons."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate (optional, clicks current position if omitted)."},
            "y": {"type": "integer", "description": "Y coordinate (optional)."},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            "clicks": {"type": "integer", "default": 1, "description": "Number of clicks."},
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "button": {"type": "string"},
            "clicks": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, x: int | None = None, y: int | None = None, button: str = "left", clicks: int = 1, **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            if x is not None and y is not None:
                ag.click(x, y, clicks=clicks, button=button)
            else:
                pos = ag.position()
                ag.click(clicks=clicks, button=button)
                x, y = pos
            return {"x": x, "y": y, "button": button, "clicks": clicks}
        except Exception as e:
            return {"error": str(e)}


class MouseScroll(Tool):
    """Scroll the mouse wheel."""

    name = "mouse_scroll"
    description = "Scroll the mouse wheel up or down."
    parameters = {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "description": "Scroll amount. Positive = up, negative = down."},
        },
        "required": ["amount"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "scrolled": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, amount: int = 3, **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            ag.scroll(amount)
            return {"scrolled": amount}
        except Exception as e:
            return {"error": str(e)}


class MouseDrag(Tool):
    """Drag from current position to target, or from one point to another."""

    name = "mouse_drag"
    description = "Drag the mouse from one position to another."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Target X coordinate."},
            "y": {"type": "integer", "description": "Target Y coordinate."},
            "duration": {"type": "number", "description": "Drag duration in seconds.", "default": 0.5},
            "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
        },
        "required": ["x", "y"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "from_x": {"type": "integer"},
            "from_y": {"type": "integer"},
            "to_x": {"type": "integer"},
            "to_y": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, x: int, y: int, duration: float = 0.5, button: str = "left", **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            start = ag.position()
            ag.dragTo(x, y, duration=duration, button=button)
            return {"from_x": start[0], "from_y": start[1], "to_x": x, "to_y": y}
        except Exception as e:
            return {"error": str(e)}


class TypeText(Tool):
    """Type text as if keyboard input."""

    name = "type_text"
    description = "Type text as keyboard input. Supports special characters and newlines."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type."},
            "interval": {"type": "number", "description": "Interval between keystrokes in seconds.", "default": 0.02},
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "typed": {"type": "string"},
            "length": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, text: str = "", interval: float = 0.02, **kwargs: Any) -> Dict[str, Any]:
        target_text = text or kwargs.get("content") or kwargs.get("value") or kwargs.get("string") or ""
        try:
            ag = _get_pyautogui()
            ag.typewrite(target_text, interval=interval) if target_text.isascii() else ag.write(target_text, interval=interval)
            return {"typed": target_text, "length": len(target_text)}
        except Exception as e:
            return {"error": str(e)}


class PressKey(Tool):
    """Press one or more keyboard keys or hotkey combinations."""

    name = "press_key"
    description = (
        "Press a key or hotkey combination. "
        "Examples: 'enter', 'ctrl+c', 'alt+tab', 'win+d', 'ctrl+shift+esc'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "string",
                "description": "Key or hotkey combo. Use + to combine: 'ctrl+c', 'alt+tab', 'win+r'.",
            },
            "presses": {"type": "integer", "default": 1, "description": "Number of times to press."},
        },
        "required": ["keys"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "pressed": {"type": "string"},
            "presses": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, keys: str, presses: int = 1, **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            presses = max(1, int(presses))
            if "+" in keys:
                # pyautogui.hotkey() has no `presses` argument; repeat the combo.
                for _ in range(presses):
                    ag.hotkey(*keys.split("+"))
            else:
                ag.press(keys, presses=presses)
            return {"pressed": keys, "presses": presses}
        except Exception as e:
            return {"error": str(e)}


class GetScreenInfo(Tool):
    """Get screen size and mouse position."""

    name = "get_screen_info"
    description = "Get screen size, mouse position, and display info."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "screen_width": {"type": "integer"},
            "screen_height": {"type": "integer"},
            "mouse_x": {"type": "integer"},
            "mouse_y": {"type": "integer"},
        },
    }

    def run(self, **_: Any) -> Dict[str, Any]:
        try:
            ag = _get_pyautogui()
            size = ag.size()
            pos = ag.position()
            return {
                "screen_width": size[0],
                "screen_height": size[1],
                "mouse_x": pos[0],
                "mouse_y": pos[1],
            }
        except Exception as e:
            return {"error": str(e)}


__all__ = [
    "MouseMove",
    "MouseClick",
    "MouseScroll",
    "MouseDrag",
    "TypeText",
    "PressKey",
    "GetScreenInfo",
]
