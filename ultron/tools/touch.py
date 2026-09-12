"""Touch input simulation for Android — tap, swipe, long-press, text input, navigation."""

from __future__ import annotations

import time
from typing import Any, Dict

from ultron.tools._termux import run_cmd
from ultron.tools.base import Tool


class TapScreen(Tool):
    """Tap a point on the screen."""

    name = "tap_screen"
    description = "Tap a specific (x, y) coordinate on the device screen."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate to tap."},
            "y": {"type": "integer", "description": "Y coordinate to tap."},
        },
        "required": ["x", "y"],
    }
    output_schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    }
    mutates = True

    def run(self, x: int = 0, y: int = 0, **kwargs: Any) -> Dict[str, Any]:
        tx = int(kwargs.get("coordinate_x") or x)
        ty = int(kwargs.get("coordinate_y") or y)
        result = run_cmd(["input", "tap", str(tx), str(ty)])
        return {"x": tx, "y": ty, "success": result.ok}


class SwipeScreen(Tool):
    """Swipe from one point to another on the screen."""

    name = "swipe_screen"
    description = "Swipe from (x1, y1) to (x2, y2) with optional duration."
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "integer", "description": "Start X coordinate."},
            "y1": {"type": "integer", "description": "Start Y coordinate."},
            "x2": {"type": "integer", "description": "End X coordinate."},
            "y2": {"type": "integer", "description": "End Y coordinate."},
            "duration_ms": {
                "type": "integer",
                "description": "Swipe duration in ms. Default 300.",
                "default": 300,
            },
        },
        "required": ["x1", "y1", "x2", "y2"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "from": {"type": "array"},
            "to": {"type": "array"},
            "duration_ms": {"type": "integer"},
        },
    }
    mutates = True

    def run(
        self, x1: int = 0, y1: int = 0, x2: int = 0, y2: int = 0,
        duration_ms: int = 300, **kwargs: Any,
    ) -> Dict[str, Any]:
        sx = int(kwargs.get("start_x") or x1)
        sy = int(kwargs.get("start_y") or y1)
        ex = int(kwargs.get("end_x") or x2)
        ey = int(kwargs.get("end_y") or y2)
        d = int(kwargs.get("duration") or kwargs.get("speed") or duration_ms)

        result = run_cmd(["input", "swipe", str(sx), str(sy), str(ex), str(ey), str(d)])
        return {"from": [sx, sy], "to": [ex, ey], "duration_ms": d, "success": result.ok}


class LongPress(Tool):
    """Long-press a point on the screen."""

    name = "long_press"
    description = "Long-press a specific (x, y) coordinate for a duration."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate."},
            "y": {"type": "integer", "description": "Y coordinate."},
            "duration_ms": {
                "type": "integer",
                "description": "Long-press duration in ms. Default 1000.",
                "default": 1000,
            },
        },
        "required": ["x", "y"],
    }
    output_schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "duration_ms": {"type": "integer"}},
    }
    mutates = True

    def run(self, x: int = 0, y: int = 0, duration_ms: int = 1000, **kwargs: Any) -> Dict[str, Any]:
        tx = int(kwargs.get("coordinate_x") or x)
        ty = int(kwargs.get("coordinate_y") or y)
        d = int(kwargs.get("duration") or duration_ms)
        # Long press is a swipe that stays in the same spot
        result = run_cmd(["input", "swipe", str(tx), str(ty), str(tx), str(ty), str(d)])
        return {"x": tx, "y": ty, "duration_ms": d, "success": result.ok}


class InputText(Tool):
    """Type text on the device keyboard."""

    name = "input_text"
    description = "Type text into the currently focused input field."
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to type.",
            },
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {"typed": {"type": "string"}, "length": {"type": "integer"}},
    }
    mutates = True

    def run(self, text: str = "", **kwargs: Any) -> Dict[str, Any]:
        t = text or kwargs.get("content") or kwargs.get("value") or ""
        if not t:
            return {"typed": "", "length": 0, "error": "No text provided"}

        result = run_cmd(["input", "text", t])
        return {"typed": t, "length": len(t), "success": result.ok}


class PressBack(Tool):
    """Press the back button."""

    name = "press_back"
    description = "Press the Android back button."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "4"])
        return {"success": result.ok}


class PressHome(Tool):
    """Press the home button."""

    name = "press_home"
    description = "Press the Android home button to go to the home screen."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "3"])
        return {"success": result.ok}


class PressRecent(Tool):
    """Press the recent apps button."""

    name = "press_recent"
    description = "Press the recent apps / multitasking button."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"success": {"type": "boolean"}},
    }
    mutates = True

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["input", "keyevent", "187"])
        return {"success": result.ok}


class PressKey(Tool):
    """Press a specific Android key by code or name."""

    name = "press_key"
    description = (
        "Press an Android key. Use key codes: enter, back, home, tab, "
        "volume_up, volume_down, power, camera, menu, delete, space, or a numeric keyevent code."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Key name or keyevent code.",
            },
        },
        "required": ["key"],
    }
    output_schema = {
        "type": "object",
        "properties": {"key": {"type": "string"}, "success": {"type": "boolean"}},
    }
    mutates = True

    def run(self, key: str = "", **kwargs: Any) -> Dict[str, Any]:
        k = key or kwargs.get("keycode") or kwargs.get("button") or ""
        if not k:
            return {"error": "No key specified", "success": False}

        KEY_MAP = {
            "enter": "66", "return": "66",
            "back": "4", "backspace": "67",
            "home": "3",
            "tab": "61",
            "volume_up": "24", "volume_down": "25",
            "power": "26",
            "camera": "27",
            "menu": "82",
            "delete": "67", "space": "62",
            "up": "19", "down": "20", "left": "21", "right": "22",
            "ok": "66", "select": "66",
            "play": "85", "pause": "85",
            "next": "87", "previous": "88",
            "search": "84",
            "escape": "111",
        }

        code = KEY_MAP.get(k.lower(), k)
        result = run_cmd(["input", "keyevent", str(code)])
        return {"key": k, "success": result.ok}


class DoubleTap(Tool):
    """Double-tap a point on the screen."""

    name = "double_tap"
    description = "Double-tap a specific (x, y) coordinate."
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate."},
            "y": {"type": "integer", "description": "Y coordinate."},
        },
        "required": ["x", "y"],
    }
    output_schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    }
    mutates = True

    def run(self, x: int = 0, y: int = 0, **kwargs: Any) -> Dict[str, Any]:
        tx = int(kwargs.get("coordinate_x") or x)
        ty = int(kwargs.get("coordinate_y") or y)
        # Two rapid taps with small delay
        run_cmd(["input", "tap", str(tx), str(ty)])
        time.sleep(0.05)
        result = run_cmd(["input", "tap", str(tx), str(ty)])
        return {"x": tx, "y": ty, "success": result.ok}


class DragAndDrop(Tool):
    """Drag from one point to another."""

    name = "drag_and_drop"
    description = "Drag from (x1, y1) to (x2, y2) with configurable duration."
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "integer", "description": "Start X."},
            "y1": {"type": "integer", "description": "Start Y."},
            "x2": {"type": "integer", "description": "End X."},
            "y2": {"type": "integer", "description": "End Y."},
            "duration_ms": {
                "type": "integer",
                "description": "Drag duration in ms. Default 500.",
                "default": 500,
            },
        },
        "required": ["x1", "y1", "x2", "y2"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "from": {"type": "array"},
            "to": {"type": "array"},
            "success": {"type": "boolean"},
        },
    }
    mutates = True

    def run(
        self, x1: int = 0, y1: int = 0, x2: int = 0, y2: int = 0,
        duration_ms: int = 500, **kwargs: Any,
    ) -> Dict[str, Any]:
        sx = int(kwargs.get("start_x") or x1)
        sy = int(kwargs.get("start_y") or y1)
        ex = int(kwargs.get("end_x") or x2)
        ey = int(kwargs.get("end_y") or y2)
        d = int(kwargs.get("duration") or duration_ms)

        result = run_cmd(["input", "draganddrop", str(sx), str(sy), str(ex), str(ey), str(d)])
        return {"from": [sx, sy], "to": [ex, ey], "success": result.ok}


__all__ = [
    "TapScreen",
    "SwipeScreen",
    "LongPress",
    "DoubleTap",
    "InputText",
    "PressBack",
    "PressHome",
    "PressRecent",
    "PressKey",
    "DragAndDrop",
]
