"""Tests for browser abstraction (Phase 4)."""

from __future__ import annotations

from ultron.browser import (
    BrowserAction,
    BrowserResult,
    BrowserTool,
    MockBrowserPage,
    MockBrowserSession,
    BROWSER_RISK_MAP,
)
from ultron.risk import RiskLevel


def test_mock_browser_page_get_url():
    page = MockBrowserPage(url="https://example.com")
    assert page.get_url() == "https://example.com"


def test_mock_browser_page_get_title():
    page = MockBrowserPage(title="Test Page")
    assert page.get_title() == "Test Page"


def test_mock_browser_page_get_text():
    page = MockBrowserPage(text="Hello World")
    assert page.get_text() == "Hello World"


def test_mock_browser_page_get_html():
    page = MockBrowserPage(title="Test", text="Content")
    html = page.get_html()
    assert "Test" in html
    assert "Content" in html


def test_mock_browser_page_click():
    page = MockBrowserPage(url="https://example.com")
    result = page.click("button#submit")
    assert result.success is True
    assert result.action == BrowserAction.CLICK


def test_mock_browser_page_fill():
    page = MockBrowserPage(url="https://example.com")
    result = page.fill("input#name", "John")
    assert result.success is True


def test_mock_browser_page_screenshot():
    page = MockBrowserPage(url="https://example.com")
    result = page.screenshot()
    assert result.success is True
    assert result.action == BrowserAction.SCREENSHOT


def test_mock_browser_session_start_stop():
    session = MockBrowserSession()
    assert session.is_running() is False
    session.start()
    assert session.is_running() is True
    session.stop()
    assert session.is_running() is False


def test_mock_browser_session_navigate():
    session = MockBrowserSession()
    session.start()
    result = session.navigate("https://example.com")
    assert result.success is True
    assert result.url == "https://example.com"
    assert session.get_page() is not None


def test_mock_browser_session_navigate_not_started():
    session = MockBrowserSession()
    result = session.navigate("https://example.com")
    assert result.success is False
    assert "not started" in result.error


def test_browser_tool_navigate():
    tool = BrowserTool()
    result = tool.navigate("https://example.com")
    assert result.success is True


def test_browser_tool_read_page():
    tool = BrowserTool()
    tool.navigate("https://example.com")
    result = tool.read_page()
    assert result.success is True
    assert "url" in result.data


def test_browser_tool_read_page_no_page():
    tool = BrowserTool()
    result = tool.read_page()
    assert result.success is False
    assert "No page loaded" in result.error


def test_browser_tool_click():
    tool = BrowserTool()
    tool.navigate("https://example.com")
    result = tool.click_element("button")
    assert result.success is True


def test_browser_tool_fill_form():
    tool = BrowserTool()
    tool.navigate("https://example.com")
    result = tool.fill_form("input", "value")
    assert result.success is True


def test_browser_tool_screenshot():
    tool = BrowserTool()
    tool.navigate("https://example.com")
    result = tool.take_screenshot()
    assert result.success is True


def test_browser_tool_get_risk_level():
    tool = BrowserTool()
    assert tool.get_risk_level(BrowserAction.READ) == RiskLevel.READ
    assert tool.get_risk_level(BrowserAction.CLICK) == RiskLevel.LOW
    assert tool.get_risk_level(BrowserAction.FILL) == RiskLevel.MEDIUM
    assert tool.get_risk_level(BrowserAction.SUBMIT) == RiskLevel.HIGH


def test_browser_risk_map_keys():
    assert BrowserAction.NAVIGATE in BROWSER_RISK_MAP
    assert BrowserAction.READ in BROWSER_RISK_MAP
    assert BrowserAction.SUBMIT in BROWSER_RISK_MAP


def test_browser_result_to_dict():
    result = BrowserResult(
        action=BrowserAction.READ,
        success=True,
        data={"text": "hello"},
        url="https://example.com",
    )
    d = result.to_dict()
    assert d["action"] == "read"
    assert d["success"] is True
