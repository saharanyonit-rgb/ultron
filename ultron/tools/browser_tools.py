"""Browser tools registered in the ToolRegistry.

These wrap BrowserTool methods as Tool instances so the orchestrator's
risk/policy gate applies to browser operations.

All tools share ONE browser session by default so a multi-step task
(navigate -> wait -> click) operates on a single, live browser instead of
several disconnected instances.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional

from ultron.browser import BrowserAction, BrowserResult, BrowserTool
from ultron.network_security import BrowserSecurityGuard, NetworkSecurityGuard
from ultron.tools.base import Tool

_shared_browser: Optional[BrowserTool] = None


def get_shared_browser() -> BrowserTool:
    """Return the process-wide browser used by all browser tools."""
    global _shared_browser
    if _shared_browser is None:
        _shared_browser = BrowserTool()
    return _shared_browser


class NavigateUrl(Tool):
    """Navigate the browser to a URL."""
    name = "navigate_url"
    description = "Navigate the browser to a URL. Security-validated."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to navigate to"},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "url": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, url: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_url = url or kwargs.get("link") or kwargs.get("uri") or kwargs.get("target") or ""
        if target_url and not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url
        result = self._browser.navigate(target_url)
        return result.to_dict()


class ReadPage(Tool):
    """Read the current browser page content."""
    name = "read_page"
    description = "Read the current browser page content (title, text, URL)."
    parameters = {
        "type": "object",
        "properties": {},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "data": {"type": "object"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, **_: Any) -> Dict[str, Any]:
        result = self._browser.read_page()
        return result.to_dict()


class ClickElement(Tool):
    """Click an element on the browser page."""
    name = "click_element"
    description = "Click an element on the current browser page by CSS selector."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector for the element"},
        },
        "required": ["selector"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, selector: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_selector = selector or kwargs.get("element") or kwargs.get("target") or kwargs.get("query") or ""
        result = self._browser.click_element(target_selector)
        return result.to_dict()


class FillFormField(Tool):
    """Fill a form field on the browser page."""
    name = "fill_form"
    description = "Fill a form field on the current browser page."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector for the input field"},
            "value": {"type": "string", "description": "Value to fill in"},
        },
        "required": ["selector", "value"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, selector: str = "", value: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_selector = selector or kwargs.get("element") or kwargs.get("field") or kwargs.get("query") or ""
        target_value = value or kwargs.get("text") or kwargs.get("input") or kwargs.get("content") or ""
        result = self._browser.fill_form(target_selector, target_value)
        return result.to_dict()


class TakeBrowserScreenshot(Tool):
    """Take a screenshot of the browser page."""
    name = "browser_screenshot"
    description = "Take a screenshot of the current browser page."
    parameters = {
        "type": "object",
        "properties": {},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "data": {"type": "object"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, **_: Any) -> Dict[str, Any]:
        result = self._browser.take_screenshot()
        return result.to_dict()


class ScrollPage(Tool):
    """Scroll the browser page up or down."""
    name = "scroll_page"
    description = "Scroll the browser page. Use 'down' or 'up' direction, and optional amount (pixels)."
    parameters = {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "description": "Scroll direction: 'down' or 'up'"},
            "amount": {"type": "integer", "description": "Pixels to scroll (default 500)"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, direction: str = "down", amount: int = 500, **kwargs: Any) -> Dict[str, Any]:
        direction = direction or kwargs.get("dir") or "down"
        amount = amount or kwargs.get("pixels") or 500
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            delta = amount if direction == "down" else -amount
            page._page.mouse.wheel(0, delta)
            return {"success": True, "scrolled": direction, "amount": amount}
        except Exception as exc:
            return {"error": str(exc)}


class PressKey(Tool):
    """Press a keyboard key in the browser."""
    name = "browser_press_key"
    description = "Press a keyboard key in the browser (Enter, Tab, Escape, ArrowDown, etc.)."
    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key to press (e.g. Enter, Tab, Escape, ArrowDown)"},
        },
        "required": ["key"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, key: str = "", **kwargs: Any) -> Dict[str, Any]:
        key = key or kwargs.get("key_name") or ""
        if not key:
            return {"error": "Missing 'key' parameter"}
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            page._page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as exc:
            return {"error": str(exc)}


class TypeText(Tool):
    """Type text into the browser (active element)."""
    name = "browser_type"
    description = "Type text into the currently focused element in the browser."
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"},
            "delay": {"type": "integer", "description": "Delay between keystrokes in ms (default 0)"},
        },
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, text: str = "", delay: int = 0, **kwargs: Any) -> Dict[str, Any]:
        text = text or kwargs.get("content") or ""
        delay = delay or kwargs.get("delay_ms") or 0
        if not text:
            return {"error": "Missing 'text' parameter"}
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            page._page.keyboard.type(text, delay=delay)
            return {"success": True, "typed": text[:50]}
        except Exception as exc:
            return {"error": str(exc)}


class HoverElement(Tool):
    """Hover over an element on the browser page."""
    name = "hover_element"
    description = "Hover the mouse over an element identified by CSS selector."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector for the element"},
        },
        "required": ["selector"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, selector: str = "", **kwargs: Any) -> Dict[str, Any]:
        selector = selector or kwargs.get("element") or ""
        if not selector:
            return {"error": "Missing 'selector' parameter"}
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            page._page.hover(selector, timeout=10000)
            return {"success": True, "selector": selector}
        except Exception as exc:
            return {"error": str(exc)}


class WaitForElement(Tool):
    """Wait for an element to appear on the page."""
    name = "wait_element"
    description = "Wait for an element to appear on the page (by CSS selector or text)."
    parameters = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS selector to wait for"},
            "timeout": {"type": "integer", "description": "Timeout in ms (default 10000)"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, selector: str = "", timeout: int = 10000, **kwargs: Any) -> Dict[str, Any]:
        selector = selector or kwargs.get("element") or ""
        timeout = timeout or kwargs.get("timeout_ms") or 10000
        if not selector:
            return {"error": "Missing 'selector' parameter"}
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            page._page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as exc:
            return {"error": str(exc)}


class GetPageLinks(Tool):
    """Get all links from the current page."""
    name = "get_page_links"
    description = "Extract all links (href) from the current browser page."
    parameters = {
        "type": "object",
        "properties": {},
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "links": {"type": "array"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, **_: Any) -> Dict[str, Any]:
        page = self._browser.session.get_page()
        if page is None:
            return {"error": "No page loaded"}
        try:
            links = page._page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({text: e.innerText.trim(), href: e.href})).filter(l => l.text)",
            )
            return {"success": True, "links": links[:100]}
        except Exception as exc:
            return {"error": str(exc)}


def get_browser_tools(
    network_guard: Optional[NetworkSecurityGuard] = None,
    browser_guard: Optional[BrowserSecurityGuard] = None,
) -> list[Tool]:
    """Create all browser tools with shared security guards."""
    bt = BrowserTool(
        network_guard=network_guard,
        browser_guard=browser_guard,
    )
    return [
        NavigateUrl(browser_tool=bt),
        ReadPage(browser_tool=bt),
        ClickElement(browser_tool=bt),
        FillFormField(browser_tool=bt),
        TakeBrowserScreenshot(browser_tool=bt),
        ScrollPage(browser_tool=bt),
        PressKey(browser_tool=bt),
        TypeText(browser_tool=bt),
        HoverElement(browser_tool=bt),
        WaitForElement(browser_tool=bt),
        GetPageLinks(browser_tool=bt),
        PlaySongTool(browser_tool=bt),
    ]


class PlaySongTool(Tool):
    """Search YouTube and start playing the first matching result."""

    name = "play_song"
    description = (
        "Play a song or music video on YouTube automatically. "
        "Provide the song name (and artist if known). The first matching result is "
        "clicked and starts playing by itself — the user does NOT need to click anything. "
        "Use whenever the user asks to play a song or music, e.g. 'play the song', "
        "'play Beat It by Michael Jackson', 'turn on some music'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "song": {
                "type": "string",
                "description": "Song title and/or artist to search for.",
            },
        },
        "required": ["song"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "playing": {"type": "boolean"},
            "song": {"type": "string"},
            "title": {"type": "string"},
            "url": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def __init__(self, browser_tool: Optional[BrowserTool] = None) -> None:
        self._browser = browser_tool or get_shared_browser()

    def run(self, song: str = "", **kwargs: Any) -> Dict[str, Any]:
        song = song or kwargs.get("title") or kwargs.get("query") or kwargs.get("name") or ""
        if not song:
            return {"success": False, "error": "Missing 'song' parameter."}

        search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(song)
        nav = self._browser.navigate(search_url)
        if not nav.success:
            return {"success": False, "error": nav.error or "Could not open YouTube."}

        page = self._browser.session.get_page()
        if page is None:
            return {"success": False, "error": "No browser page available."}

        click = self._click_first_result(page)
        if not click.success:
            return {
                "success": False,
                "error": click.error
                or "Could not find any matching video. Try a more specific song name.",
            }

        title = self._clean_title(page.get_title())
        page_url = page.get_url()
        return {
            "success": True,
            "playing": True,
            "song": song,
            "title": title,
            "url": page_url or search_url,
        }

    @staticmethod
    def _click_first_result(page: Any) -> BrowserResult:
        """Click the first YouTube search result, waiting for it to render."""
        raw = getattr(page, "_page", None)
        selectors = [
            "ytd-video-renderer a#video-title",
            "ytd-video-renderer a#thumbnail",
            "a#video-title",
        ]
        for selector in selectors:
            if raw is not None:
                try:
                    raw.wait_for_selector(selector, timeout=15000)
                except Exception:
                    continue
            result = page.click(selector)
            if result.success:
                # Wait for navigation to the watch page so playback actually begins.
                if raw is not None:
                    try:
                        raw.wait_for_url("**/watch*", timeout=20000)
                    except Exception:
                        pass
                return result
        return BrowserResult(action=BrowserAction.CLICK, success=False, error="no video results found")

    @staticmethod
    def _clean_title(title: str) -> str:
        return (title or "").removesuffix(" - YouTube").strip()


__all__ = [
    "NavigateUrl",
    "ReadPage",
    "ClickElement",
    "FillFormField",
    "TakeBrowserScreenshot",
    "ScrollPage",
    "PressKey",
    "TypeText",
    "HoverElement",
    "WaitForElement",
    "GetPageLinks",
    "PlaySongTool",
    "get_browser_tools",
    "get_shared_browser",
]
