"""Media control tools for Android — play, pause, skip, volume, media info."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux, run_cmd
from ultron.tools.base import Tool


class PlayMedia(Tool):
    """Play audio or media via termux-media-player."""

    name = "play_media"
    description = "Play a media file (audio/video) by file path or URL."
    parameters = {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "File path or URL to play.",
            },
        },
        "required": ["source"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "source": {"type": "string"},
        },
    }
    mutates = True

    def run(self, source: str = "", **kwargs: Any) -> Dict[str, Any]:
        src = source or kwargs.get("url") or kwargs.get("path") or kwargs.get("file") or ""
        if not src:
            return {"error": "No media source specified", "success": False}
        result = run_termux("media-player", args=["play", src])
        return {"success": result.ok, "source": src, "error": result.stderr or None}


class PauseMedia(Tool):
    """Pause the currently playing media."""

    name = "pause_media"
    description = "Pause the currently playing media."
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
        result = run_termux("media-player", args=["pause"])
        return {"success": result.ok}


class StopMedia(Tool):
    """Stop the currently playing media."""

    name = "stop_media"
    description = "Stop the currently playing media."
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
        result = run_termux("media-player", args=["stop"])
        return {"success": result.ok}


class SkipNext(Tool):
    """Skip to the next track."""

    name = "skip_next"
    description = "Skip to the next media track."
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
        result = run_cmd(["input", "keyevent", "87"])
        return {"success": result.ok}


class SkipPrevious(Tool):
    """Skip to the previous track."""

    name = "skip_previous"
    description = "Skip to the previous media track."
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
        result = run_cmd(["input", "keyevent", "88"])
        return {"success": result.ok}


class PlayPause(Tool):
    """Toggle play/pause on media."""

    name = "play_pause"
    description = "Toggle play/pause on the current media player."
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
        # Key event 85 is MEDIA_PLAY_PAUSE
        result = run_cmd(["input", "keyevent", "85"])
        return {"success": result.ok}


class GetMediaInfo(Tool):
    """Get currently playing media information."""

    name = "get_media_info"
    description = "Get information about the currently playing media track."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "is_playing": {"type": "boolean"},
            "title": {"type": "string"},
            "artist": {"type": "string"},
            "album": {"type": "string"},
            "duration_ms": {"type": "integer"},
            "position_ms": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        # Use dumpsys media_session to get current media info
        result = run_cmd(["dumpsys", "media_session"])
        if not result.ok:
            return {"is_playing": False, "error": result.stderr}

        info = {
            "is_playing": False,
            "title": "",
            "artist": "",
            "album": "",
            "duration_ms": 0,
            "position_ms": 0,
        }

        stdout = result.stdout
        for line in stdout.split("\n"):
            line_s = line.strip()
            if line_s.startswith("state=PlaybackState"):
                info["is_playing"] = "state=3" in line_s or "playback" in line_s.lower()
            elif "title=" in line_s:
                info["title"] = line_s.split("title=", 1)[-1].strip().strip('"')
            elif "artist=" in line_s:
                info["artist"] = line_s.split("artist=", 1)[-1].strip().strip('"')
            elif "album=" in line_s:
                info["album"] = line_s.split("album=", 1)[-1].strip().strip('"')

        return info


class VibrateDevice(Tool):
    """Vibrate the device for a duration."""

    name = "vibrate_device"
    description = "Vibrate the device for a specified duration."
    parameters = {
        "type": "object",
        "properties": {
            "duration_ms": {
                "type": "integer",
                "description": "Vibration duration in milliseconds. Default 500.",
                "default": 500,
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "duration_ms": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, duration_ms: int = 500, **kwargs: Any) -> Dict[str, Any]:
        d = kwargs.get("duration") or kwargs.get("time") or duration_ms
        result = run_termux("vibrate", args=["-d", str(int(d))])
        return {"success": result.ok, "duration_ms": int(d)}


class ShowToast(Tool):
    """Show a toast message on the device screen."""

    name = "show_toast"
    description = "Display a short toast message at the bottom of the screen."
    parameters = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message to display in the toast.",
            },
        },
        "required": ["message"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
        },
    }
    mutates = True

    def run(self, message: str = "", **kwargs: Any) -> Dict[str, Any]:
        msg = message or kwargs.get("text") or kwargs.get("content") or ""
        if not msg:
            return {"error": "No message provided", "success": False}
        result = run_termux("toast", args=[msg])
        return {"success": result.ok, "message": msg}


__all__ = [
    "PlayMedia",
    "PauseMedia",
    "StopMedia",
    "SkipNext",
    "SkipPrevious",
    "PlayPause",
    "GetMediaInfo",
    "VibrateDevice",
    "ShowToast",
]
