"""V1 screenshot tool — captures the primary screen using System.Drawing."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ultron.tools._windows import ps_error, ps_ok, ps_quote, run_powershell
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
