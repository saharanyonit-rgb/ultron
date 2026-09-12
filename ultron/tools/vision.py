"""Vision tool — captures screen and analyzes it with vision-capable LLM — cross-platform."""

from __future__ import annotations

import base64
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ultron.platform import is_windows
from ultron.tools.base import Tool, ToolError

logger = logging.getLogger("ultron.tools.vision")


class VisionTool(Tool):
    """Capture the screen and analyze it with a vision-capable LLM."""

    name = "vision_analyze"
    description = (
        "Capture the screen and analyze it with a vision-capable LLM. "
        "Use this when the user asks to look at the screen, check what's displayed, "
        "analyze the current view, or describe what you see. "
        "Returns a detailed description of all visible UI elements, text, and context."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "What to look for or analyze in the screenshot. "
                    "Examples: 'What window is focused?', 'Describe all visible text', "
                    "'Is there a dialog open?', 'What application is running?'"
                ),
            },
            "path": {
                "type": "string",
                "description": "Optional path to save the screenshot PNG.",
            },
        },
        "required": ["prompt"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "analysis": {"type": "string"},
            "screenshot_path": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(self, prompt: str, path: Optional[str] = None, **_: Any) -> Dict[str, Any]:
        screenshot_result = self._capture_screen(path)
        if "error" in screenshot_result:
            return screenshot_result

        screenshot_path = screenshot_result["path"]

        analysis = self._analyze_image(screenshot_path, prompt)
        if "error" in analysis:
            return analysis

        return {
            "analysis": analysis.get("analysis", ""),
            "screenshot_path": screenshot_path,
            "width": screenshot_result["width"],
            "height": screenshot_result["height"],
        }

    def _capture_screen(self, path: Optional[str]) -> Dict[str, Any]:
        if path:
            target = Path(path).expanduser()
            if target.suffix.lower() != ".png":
                target = target.with_suffix(".png")
        else:
            pictures = Path.home() / "Pictures"
            target = pictures / f"ultron-vision-{datetime.now():%Y%m%d-%H%M%S}.png"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"error": f"cannot create screenshot directory: {exc}"}

        if is_windows():
            return self._capture_windows(target)
        return self._capture_posix(target)

    def _capture_windows(self, target: Path) -> Dict[str, Any]:
        from ultron.tools._windows import ps_error, ps_ok, ps_quote, run_powershell

        script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
            "$bmp.Save(" + ps_quote(str(target)) + ", [System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose(); "
            "Write-Output ($b.Width.ToString() + 'x' + $b.Height.ToString())"
        )
        proc = run_powershell(script, timeout=60)
        if not ps_ok(proc):
            return {"error": f"screenshot failed: {ps_error(proc)}"}
        if not target.is_file():
            return {"error": f"screenshot reported success but no file at {target}"}
        try:
            width, height = proc.stdout.strip().split("x")
            width, height = int(width), int(height)
        except ValueError:
            width, height = 0, 0
        return {"path": str(target), "width": width, "height": height}

    def _capture_posix(self, target: Path) -> Dict[str, Any]:
        """Take screenshot on Linux/Android using available tools."""
        tools = [
            (["scrot", str(target)], None),
            (["maim", str(target)], None),
            (["gnome-screenshot", "-f", str(target)], None),
            (["termux-screenshot", str(target)], None),
            (["import", "-window", "root", str(target)], None),
        ]

        for cmd, _ in tools:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=15,
                )
                if proc.returncode == 0 and target.is_file():
                    return {"path": str(target), "width": 0, "height": 0}
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return {"error": "No screenshot tool available. Install scrot, maim, or termux-api."}

    def _analyze_image(self, image_path: str, prompt: str) -> Dict[str, Any]:
        try:
            from ultron.llm import build_provider
            from ultron.config import load_config, ConfigError
        except Exception as exc:
            return {"error": f"cannot import LLM provider: {exc}"}

        try:
            config = load_config()
        except ConfigError:
            return {"error": "LLM not configured (set GOOGLE_API_KEY in .env)"}

        try:
            provider = build_provider(config)
        except Exception as exc:
            return {"error": f"failed to initialize LLM provider: {exc}"}

        supports_vision = getattr(provider, "supports_vision", False)
        if not supports_vision:
            return {
                "error": (
                    f"Vision not supported by {config.provider} provider. "
                    "Use Gemini 1.5 Pro or later which supports vision."
                )
            }

        analyze_method = getattr(provider, "analyze_image", None)
        if not analyze_method:
            return {"error": "LLM provider does not have vision analysis capability."}

        try:
            result = analyze_method(image_path, prompt)
            return {"analysis": result}
        except Exception as exc:
            logger.error("Vision analysis failed: %s", exc)
            return {"error": f"vision analysis failed: {exc}"}
