"""Browser tools registered in the ToolRegistry.

These wrap BrowserTool methods as Tool instances so the orchestrator's
risk/policy gate applies to browser operations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ultron.browser import BrowserTool, BrowserAction
from ultron.network_security import BrowserSecurityGuard, NetworkSecurityGuard
from ultron.tools.base import Tool


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
        self._browser = browser_tool or BrowserTool()

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
        self._browser = browser_tool or BrowserTool()

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
        self._browser = browser_tool or BrowserTool()

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
        self._browser = browser_tool or BrowserTool()

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
        self._browser = browser_tool or BrowserTool()

    def run(self, **_: Any) -> Dict[str, Any]:
        result = self._browser.take_screenshot()
        return result.to_dict()


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
    ]


__all__ = [
    "NavigateUrl",
    "ReadPage",
    "ClickElement",
    "FillFormField",
    "TakeBrowserScreenshot",
    "get_browser_tools",
]
