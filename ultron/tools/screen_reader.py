"""Screen reader tools — accessibility UI dump and screenshot-based vision analysis."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.tools._termux import run_cmd, run_termux, run_raw
from ultron.tools.base import Tool

logger = logging.getLogger("ultron.tools.screen_reader")

# Dumpsys UI dump requires shell access; screenshot + AI is universal


class GetUiDump(Tool):
    """Dump the current UI hierarchy using uiautomator (requires shell access)."""

    name = "get_ui_dump"
    description = "Get the full UI accessibility tree of the current screen. Requires uiautomator2 or shell access."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "elements": {"type": "array"},
            "count": {"type": "integer"},
            "method": {"type": "string"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        # Try uiautomator2 (if pip-installed)
        try:
            result = run_cmd(["python3", "-c",
                "import uiautomator2 as u2; "
                "d = u2.connect(); "
                "import json; "
                "info = d.dump_hierarchy(); "
                "print(json.dumps({'xml': info[:50000]}))"
            ])
            if result.ok and result.stdout.strip():
                data = json.loads(result.stdout)
                elements = _parse_ui_xml(data.get("xml", ""))
                return {"elements": elements, "count": len(elements), "method": "uiautomator2"}
        except Exception:
            pass

        # Fallback: use Android dumpsys
        result = run_cmd(["dumpsys", "window", "windows"])
        if result.ok:
            windows = _parse_dumpsys_windows(result.stdout)
            return {"elements": windows, "count": len(windows), "method": "dumpsys"}

        return {"elements": [], "count": 0, "error": "No UI dump method available. Install uiautomator2: pip install uiautomator2"}


class ClickUiElement(Tool):
    """Find a UI element by text/description and tap it."""

    name = "click_ui_element"
    description = "Find a UI element by text, description, or class and tap its center."
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text or content-desc of the element to find and tap.",
            },
            "element_class": {
                "type": "string",
                "description": "Optional: filter by class name (e.g. 'android.widget.Button').",
            },
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "found": {"type": "boolean"},
            "text": {"type": "string"},
            "center_x": {"type": "integer"},
            "center_y": {"type": "integer"},
        },
    }
    mutates = True

    def run(self, text: str = "", element_class: str = "", **kwargs: Any) -> Dict[str, Any]:
        t = text or kwargs.get("element_text") or kwargs.get("label") or kwargs.get("description") or ""
        if not t:
            return {"error": "No text to search for", "success": False, "found": False}

        # Try uiautomator2
        try:
            import subprocess
            # json.dumps produces a safe double-quoted Python string literal,
            # preventing single-quote/backslash escaping bugs and code injection.
            target = json.dumps(t)
            code = (
                "import uiautomator2 as u2; "
                "d = u2.connect(); "
                f"el = d(text={target}); "
                "if el.exists: "
                "  info = el.info; "
                "  print(info.get('bounds', {})) "
                "else: print({})"
            )
            result = run_cmd(["python3", "-c", code])
            if result.ok:
                bounds_str = result.stdout.strip()
                if bounds_str and bounds_str != "{}":
                    try:
                        bounds = json.loads(bounds_str)
                    except (json.JSONDecodeError, TypeError):
                        return {
                            "success": False, "found": False, "text": t,
                            "error": "UI element bounds were not parseable.",
                        }
                    cx = (bounds.get("left", 0) + bounds.get("right", 0)) // 2
                    cy = (bounds.get("top", 0) + bounds.get("bottom", 0)) // 2
                    # Tap it
                    run_cmd(["input", "tap", str(cx), str(cy)])
                    return {
                        "success": True, "found": True, "text": t,
                        "center_x": cx, "center_y": cy,
                    }
        except Exception:
            pass

        # Fallback: AI vision approach
        return {
            "success": False, "found": False, "text": t,
            "error": "Could not locate element. Try using take_screenshot + AI vision.",
        }


class ReadScreen(Tool):
    """Take a screenshot and describe the screen contents using AI vision."""

    name = "read_screen"
    description = "Capture a screenshot and analyze it to describe what's on screen."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look for on screen (optional).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "screenshot_path": {"type": "string"},
            "description": {"type": "string"},
            "elements": {"type": "array"},
        },
    }

    def run(self, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        # Take screenshot
        screenshot_dir = Path.home() / "Pictures" / "ultron"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / "screen_read.png"

        result = run_cmd(["termux-screenshot", str(screenshot_path)])
        if not result.ok:
            return {"error": f"Screenshot failed: {result.stderr}", "screenshot_path": ""}

        if not screenshot_path.exists():
            return {"error": "Screenshot file not created", "screenshot_path": ""}

        # Use AI vision to describe
        description = self._analyze_screenshot(str(screenshot_path), query)

        return {
            "screenshot_path": str(screenshot_path),
            "description": description,
            "size_bytes": screenshot_path.stat().st_size,
        }

    def _analyze_screenshot(self, path: str, query: str) -> str:
        """Use vision model to analyze the screenshot."""
        try:
            from ultron.config import load_config
            from ultron.llm import build_provider

            config = load_config()
            provider = build_provider(config)

            prompt = (
                f"Describe what's on this Android phone screen. "
                f"If elements are visible, list them with approximate screen coordinates (x, y). "
            )
            if query:
                prompt += f"Specifically, identify: {query}. "

            prompt += (
                "Format your response as:\n"
                "SCREEN CONTENT:\n<what you see>\n"
                "ELEMENTS:\n- <element> at (<x>, <y>) [type: button/text/field/etc]"
            )

            result = provider.complete([
                {"role": "user", "content": prompt, "image": path}
            ])
            return result.get("text", "Could not analyze screenshot")
        except Exception as e:
            return f"Vision analysis unavailable: {e}"


class GetScreenResolution(Tool):
    """Get the exact screen resolution of the device."""

    name = "get_screen_resolution"
    description = "Get the exact screen resolution in pixels."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "width": {"type": "integer"},
            "height": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["wm", "size"])
        if result.ok:
            # Output: "Physical size: 1080x2400"
            output = result.stdout.strip()
            for line in output.split("\n"):
                if "size" in line.lower():
                    parts = line.split(":")[-1].strip().split("x")
                    if len(parts) == 2:
                        try:
                            return {"width": int(parts[0]), "height": int(parts[1])}
                        except ValueError:
                            pass
        return {"width": 0, "height": 0, "error": result.stderr}


class GetScreenDensity(Tool):
    """Get screen density (DPI)."""

    name = "get_screen_density"
    description = "Get the device screen density in DPI."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "density": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["wm", "density"])
        if result.ok:
            output = result.stdout.strip()
            for line in output.split("\n"):
                if "density" in line.lower():
                    parts = line.split(":")[-1].strip()
                    try:
                        return {"density": int(parts)}
                    except ValueError:
                        pass
        return {"density": 0, "error": result.stderr}


def _parse_ui_xml(xml_str: str) -> List[Dict[str, Any]]:
    """Parse uiautomator XML into a list of element dicts."""
    elements = []
    import re
    nodes = re.findall(r'<node\s+([^>]+?)/?>', xml_str)
    for node in nodes:
        attrs = {}
        for match in re.finditer(r'(\w[\w-]*)="([^"]*)"', node):
            attrs[match.group(1)] = match.group(2)

        bounds_str = attrs.get("bounds", "")
        bounds = {}
        bounds_match = re.findall(r'\[(\d+),(\d+)\]', bounds_str)
        if len(bounds_match) == 2:
            bounds = {
                "left": int(bounds_match[0][0]),
                "top": int(bounds_match[0][1]),
                "right": int(bounds_match[1][0]),
                "bottom": int(bounds_match[1][1]),
            }

        elements.append({
            "class": attrs.get("class", ""),
            "text": attrs.get("text", ""),
            "content-desc": attrs.get("content-desc", ""),
            "resource-id": attrs.get("resource-id", ""),
            "clickable": attrs.get("clickable", "false") == "true",
            "bounds": bounds,
        })

    return elements


def _parse_dumpsys_windows(output: str) -> List[Dict[str, Any]]:
    """Parse dumpsys window output into a list of visible windows."""
    windows = []
    for line in output.split("\n"):
        line = line.strip()
        if "Window #" in line:
            windows.append({
                "type": "window",
                "text": line,
                "clickable": False,
            })
    return windows[:50]


__all__ = [
    "GetUiDump",
    "ClickUiElement",
    "ReadScreen",
    "GetScreenResolution",
    "GetScreenDensity",
]
