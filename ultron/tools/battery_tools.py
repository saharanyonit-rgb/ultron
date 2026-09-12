"""Battery, WiFi, Bluetooth, and system settings tools for Android."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import (
    run_termux, run_cmd, run_settings, run_raw, run_am,
)
from ultron.tools.base import Tool


class GetBatteryInfo(Tool):
    """Get battery status and level."""

    name = "get_battery"
    description = "Get current battery level, health, temperature, and charging status."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "level": {"type": "integer"},
            "health": {"type": "string"},
            "status": {"type": "string"},
            "plugged": {"type": "string"},
            "temperature": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("battery-status", parse_json=True)
        if not result.ok:
            return {"error": result.stderr, "level": -1}

        data = result.data if isinstance(result.data, dict) else {}
        return {
            "level": data.get("percentage", -1),
            "health": data.get("health", "unknown"),
            "status": data.get("status", "unknown"),
            "plugged": data.get("plugged", "unknown"),
            "temperature": data.get("temperature", 0),
            "voltage": data.get("voltage", 0),
        }


class ToggleWifi(Tool):
    """Enable or disable WiFi."""

    name = "toggle_wifi"
    description = "Turn WiFi on or off."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable WiFi, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, enabled: bool = True, **kwargs: Any) -> Dict[str, Any]:
        state = kwargs.get("state") or kwargs.get("on") or enabled
        if isinstance(state, str):
            state = state.lower() in ("true", "on", "1", "yes", "enable")
        result = run_termux("wifi-enable" if state else "wifi-disable")
        return {"success": result.ok, "enabled": state, "error": result.stderr or None}


class ToggleBluetooth(Tool):
    """Enable or disable Bluetooth."""

    name = "toggle_bluetooth"
    description = "Turn Bluetooth on or off."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, enabled: bool = True, **kwargs: Any) -> Dict[str, Any]:
        state = kwargs.get("state") or kwargs.get("on") or enabled
        if isinstance(state, str):
            state = state.lower() in ("true", "on", "1", "yes", "enable")

        action = "android.bluetooth.adapter.action.REQUEST_ENABLE" if state \
            else "android.bluetooth.adapter.action.REQUEST_DISABLE"
        result = run_am(["start", "-a", action])
        return {"success": result.ok, "enabled": state, "error": result.stderr or None}


class ToggleAirplane(Tool):
    """Enable or disable airplane mode."""

    name = "toggle_airplane"
    description = "Turn airplane mode on or off."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable airplane mode, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, enabled: bool = True, **kwargs: Any) -> Dict[str, Any]:
        state = kwargs.get("state") or kwargs.get("on") or enabled
        if isinstance(state, str):
            state = state.lower() in ("true", "on", "1", "yes", "enable")

        value = "1" if state else "0"
        result = run_settings(["put", "global", "airplane_mode_on", value])
        # Also broadcast the change
        run_cmd(["am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE",
                 "--ez", "state", str(state).lower()])
        return {"success": result.ok, "enabled": state, "error": result.stderr or None}


class SetBrightness(Tool):
    """Set screen brightness level."""

    name = "set_brightness"
    description = "Set screen brightness (0-255)."
    parameters = {
        "type": "object",
        "properties": {
            "level": {
                "type": "integer",
                "description": "Brightness level from 0 (min) to 255 (max).",
            },
        },
        "required": ["level"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "level": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, level: int = 128, **kwargs: Any) -> Dict[str, Any]:
        lv = kwargs.get("value") or kwargs.get("brightness") or level
        lv = max(0, min(255, int(lv)))
        result = run_termux("brightness", args=[str(lv)])
        return {"success": result.ok, "level": lv, "error": result.stderr or None}


class SetVolume(Tool):
    """Set system volume for a specific stream."""

    name = "set_volume"
    description = "Set volume level for a stream (ring, notification, music, alarm, call, system)."
    parameters = {
        "type": "object",
        "properties": {
            "stream": {
                "type": "string",
                "description": "Audio stream: ring, notification, music, alarm, call, system.",
                "enum": ["ring", "notification", "music", "alarm", "call", "system"],
            },
            "level": {
                "type": "integer",
                "description": "Volume level (0-15).",
            },
        },
        "required": ["stream", "level"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "stream": {"type": "string"},
            "level": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, stream: str = "notification", level: int = 10, **kwargs: Any) -> Dict[str, Any]:
        s = kwargs.get("type") or kwargs.get("audio_stream") or stream
        lv = kwargs.get("value") or kwargs.get("volume") or level
        lv = max(0, min(15, int(lv)))

        result = run_termux("volume", args=[s, str(lv)])
        return {"success": result.ok, "stream": s, "level": lv, "error": result.stderr or None}


class GetVolume(Tool):
    """Get current volume levels for all streams."""

    name = "get_volume"
    description = "Get current volume level for a specific stream or all streams."
    parameters = {
        "type": "object",
        "properties": {
            "stream": {
                "type": "string",
                "description": "Stream to check. Omit for all.",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "volumes": {"type": "object"},
        },
    }

    def run(self, stream: str = "", **kwargs: Any) -> Dict[str, Any]:
        s = kwargs.get("type") or stream or ""
        args = [s] if s else []
        result = run_termux("volume", args=args, parse_json=True)
        if not result.ok:
            return {"volumes": {}, "error": result.stderr}
        return {"volumes": result.data}


class ToggleData(Tool):
    """Enable or disable mobile data."""

    name = "toggle_data"
    description = "Turn mobile data on or off (requires root or ADB)."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, enabled: bool = True, **kwargs: Any) -> Dict[str, Any]:
        state = kwargs.get("state") or kwargs.get("on") or enabled
        if isinstance(state, str):
            state = state.lower() in ("true", "on", "1", "yes", "enable")

        value = "1" if state else "0"
        result = run_settings(["put", "global", "mobile_data", value])
        return {"success": result.ok, "enabled": state, "error": result.stderr or None}


class ToggleDoNotDisturb(Tool):
    """Enable or disable Do Not Disturb mode."""

    name = "toggle_dnd"
    description = "Turn Do Not Disturb mode on or off."
    parameters = {
        "type": "object",
        "properties": {
            "enabled": {
                "type": "boolean",
                "description": "True to enable DND, False to disable.",
            },
        },
        "required": ["enabled"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "enabled": {"type": "boolean"},
        },
    }
    mutates = True

    def run(self, enabled: bool = True, **kwargs: Any) -> Dict[str, Any]:
        state = kwargs.get("state") or kwargs.get("on") or enabled
        if isinstance(state, str):
            state = state.lower() in ("true", "on", "1", "yes", "enable")

        # Android `zen_mode` is numeric: 0=off, 1=important, 2=alarms, 3=full.
        value = "3" if state else "0"
        result = run_settings(["put", "global", "zen_mode", value])
        return {"success": result.ok, "enabled": state, "error": result.stderr or None}


class ScreenOn(Tool):
    """Turn the screen on."""

    name = "screen_on"
    description = "Turn the device screen on."
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
        result = run_cmd(["input", "keyevent", "224"])
        return {"success": result.ok}


class ScreenOff(Tool):
    """Turn the screen off."""

    name = "screen_off"
    description = "Turn the device screen off."
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
        result = run_cmd(["input", "keyevent", "223"])
        return {"success": result.ok}


class UnlockScreen(Tool):
    """Unlock the screen (swipe up to dismiss lock screen)."""

    name = "unlock_screen"
    description = "Unlock the device by swiping up on the lock screen."
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
        # Turn on screen first
        run_cmd(["input", "keyevent", "224"])
        import time
        time.sleep(0.5)
        # Swipe up
        result = run_cmd(["input", "swipe", "540", "1800", "540", "400", "300"])
        return {"success": result.ok}


__all__ = [
    "GetBatteryInfo",
    "ToggleWifi",
    "ToggleBluetooth",
    "ToggleAirplane",
    "ToggleData",
    "ToggleDoNotDisturb",
    "SetBrightness",
    "SetVolume",
    "GetVolume",
    "ScreenOn",
    "ScreenOff",
    "UnlockScreen",
]
