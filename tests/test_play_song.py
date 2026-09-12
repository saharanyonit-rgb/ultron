"""Tests for music playback and shared-browser behavior."""

from __future__ import annotations

import pytest

from ultron.browser import BrowserAction, BrowserResult
from ultron.tools import ALL_TOOLS, ToolRegistry
from ultron.tools.browser_tools import PlaySongTool, get_shared_browser, get_browser_tools


@pytest.fixture(autouse=True)
def _reset_shared_browser():
    import ultron.tools.browser_tools as bt_mod

    old = bt_mod._shared_browser
    bt_mod._shared_browser = None
    yield
    bt_mod._shared_browser = old


class FakePage:
    def __init__(self, title="Beat It - Michael Jackson - YouTube", url="https://www.youtube.com/watch?v=abc"):
        self._page = None  # signals "no live playwright page"
        self._title = title
        self._url = url
        self.clicked = []

    def get_title(self):
        return self._title

    def get_url(self):
        return self._url

    def click(self, selector):
        self.clicked.append(selector)
        return BrowserResult(action=BrowserAction.CLICK, success=True, url=self._url)


class FakePageNoResults(FakePage):
    def click(self, selector):
        return BrowserResult(action=BrowserAction.CLICK, success=False, error="selector not found")


class FakeBrowser:
    def __init__(self, page=None, nav_error=""):
        self._page = page or FakePage()
        self.nav_error = nav_error
        self.navigated = None

    @property
    def session(self):
        return self

    def get_page(self):
        return self._page

    def navigate(self, url):
        self.navigated = url
        if self.nav_error:
            return BrowserResult(action=BrowserAction.NAVIGATE, success=False, error=self.nav_error)
        return BrowserResult(action=BrowserAction.NAVIGATE, success=True, url=url)


def test_play_song_navigates_and_clicks_first_result():
    page = FakePage()
    tool = PlaySongTool(browser_tool=FakeBrowser(page=page))

    result = tool.run(song="beat it michael jackson")

    assert result["success"] is True
    assert result["playing"] is True
    assert "beat%20it" in tool._browser.navigated.lower() or "beat+it" in tool._browser.navigated.lower()
    assert page.clicked, "first result should have been clicked"
    assert result["title"] == "Beat It - Michael Jackson"
    assert result["url"].startswith("https://www.youtube.com/watch")


def test_play_song_missing_song_returns_error():
    tool = PlaySongTool(browser_tool=FakeBrowser())
    result = tool.run(song="")
    assert result["success"] is False
    assert "song" in result["error"].lower()


def test_play_song_navigation_failure():
    tool = PlaySongTool(browser_tool=FakeBrowser(nav_error="blocked"))
    result = tool.run(song="hello")
    assert result["success"] is False
    assert "blocked" in result["error"]


def test_play_song_no_results():
    tool = PlaySongTool(browser_tool=FakeBrowser(page=FakePageNoResults()))
    result = tool.run(song="nonexistent song xyz")
    assert result["success"] is False
    assert "video" in result["error"].lower() or "results" in result["error"].lower()


def test_shared_browser_is_singleton():
    assert get_shared_browser() is get_shared_browser()


def test_browser_tools_share_one_browser():
    tools = get_browser_tools()
    browsers = {id(t._browser) for t in tools}
    assert len(browsers) == 1


def test_play_song_registered_in_tool_registry():
    registry = ToolRegistry(ALL_TOOLS)
    assert registry.exists("play_song")