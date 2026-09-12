"""V1 screenshot tool — cross-platform (Windows System.Drawing, Linux scrot/maim)."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ultron.platform import is_windows, is_posix
from ultron.tools.base import Tool


class TakeScreenshot(Tool):
    name = "take_screenshot"
    description = (
        "Capture the primary screen to a PNG file and report the saved path. "
        "Defaults to ~/Pictures when no path is given."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional absolute path for the PNG file.",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "bytes": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, path: str | None = None, **_: Any) -> Dict[str, Any]:
        if path:
            target = Path(path).expanduser()
            if target.suffix.lower() != ".png":
                target = target.with_suffix(".png")
        else:
            pictures = Path.home() / "Pictures"
            target = pictures / f"ultron-{datetime.now():%Y%m%d-%H%M%S}.png"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return {"error": f"cannot create screenshot directory: {exc}"}

        if is_windows():
            return self._screenshot_windows(target)
        return self._screenshot_posix(target)

    def _screenshot_windows(self, target: Path) -> Dict[str, Any]:
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
        return {
            "path": str(target),
            "width": width,
            "height": height,
            "bytes": target.stat().st_size,
        }

    def _screenshot_posix(self, target: Path) -> Dict[str, Any]:
        """Take screenshot on Linux/Android using available tools."""
        # Try common screenshot tools in order
        tools = [
            # scrot (common on Linux)
            (["scrot", str(target)], None),
            # maim (alternative)
            (["maim", str(target)], None),
            # gnome-screenshot
            (["gnome-screenshot", "-f", str(target)], None),
            # Termux screenshot (requires termux-api)
            (["termux-screenshot", str(target)], None),
            # import (ImageMagick)
            (["import", "-window", "root", str(target)], None),
        ]

        for cmd, _ in tools:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=15,
                )
                if proc.returncode == 0 and target.is_file():
                    return {
                        "path": str(target),
                        "width": 0,
                        "height": 0,
                        "bytes": target.stat().st_size,
                    }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        return {"error": "No screenshot tool available. Install scrot, maim, or termux-api."}
