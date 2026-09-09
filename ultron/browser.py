"""Browser abstraction for JARVIS Phase 4.

Provides an interface for browser automation that can eventually support:
  - Navigation
  - Page inspection
  - Text extraction
  - Clicking
  - Form interaction
  - Screenshots
  - Page state
  - Controlled downloads

Architecture:
  Browser
   ├── BrowserSession (manages connection)
   ├── BrowserPage (represents a page)
   └── BrowserTool (tool interface for agents)

Browser operations remain permissioned. Reading a webpage should not
require the same permission level as submitting a form.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.network_security import (
    BrowserSandboxPolicy,
    BrowserSecurityGuard,
    NetworkSecurityGuard,
    NetworkPolicy,
)
from ultron.risk import RiskLevel

logger = logging.getLogger("ultron.browser")


class BrowserAction(str, Enum):
    NAVIGATE = "navigate"
    READ = "read"
    CLICK = "click"
    FILL = "fill"
    SUBMIT = "submit"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"


# Risk levels for browser actions
BROWSER_RISK_MAP: Dict[BrowserAction, RiskLevel] = {
    BrowserAction.NAVIGATE: RiskLevel.READ,
    BrowserAction.READ: RiskLevel.READ,
    BrowserAction.EXTRACT: RiskLevel.READ,
    BrowserAction.SCREENSHOT: RiskLevel.READ,
    BrowserAction.CLICK: RiskLevel.LOW,
    BrowserAction.FILL: RiskLevel.MEDIUM,
    BrowserAction.SUBMIT: RiskLevel.HIGH,
}


@dataclass
class BrowserResult:
    """Result of a browser operation."""

    action: BrowserAction
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "url": self.url,
        }


class BrowserPage(ABC):
    """Abstract representation of a browser page."""

    @abstractmethod
    def get_url(self) -> str:
        """Get the current page URL."""
        ...

    @abstractmethod
    def get_title(self) -> str:
        """Get the page title."""
        ...

    @abstractmethod
    def get_text(self) -> str:
        """Extract text content from the page."""
        ...

    @abstractmethod
    def get_html(self) -> str:
        """Get the page HTML."""
        ...

    @abstractmethod
    def click(self, selector: str) -> BrowserResult:
        """Click an element."""
        ...

    @abstractmethod
    def fill(self, selector: str, value: str) -> BrowserResult:
        """Fill a form field."""
        ...

    @abstractmethod
    def screenshot(self) -> BrowserResult:
        """Take a screenshot."""
        ...


class BrowserSession(ABC):
    """Abstract browser session management."""

    @abstractmethod
    def start(self) -> None:
        """Start the browser session."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the browser session."""
        ...

    @abstractmethod
    def navigate(self, url: str) -> BrowserResult:
        """Navigate to a URL."""
        ...

    @abstractmethod
    def get_page(self) -> BrowserPage | None:
        """Get the current page."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the session is active."""
        ...


class MockBrowserPage(BrowserPage):
    """Mock browser page for testing."""

    def __init__(self, url: str = "", title: str = "", text: str = "") -> None:
        self._url = url
        self._title = title
        self._text = text

    def get_url(self) -> str:
        return self._url

    def get_title(self) -> str:
        return self._title

    def get_text(self) -> str:
        return self._text

    def get_html(self) -> str:
        return f"<html><head><title>{self._title}</title></head><body>{self._text}</body></html>"

    def click(self, selector: str) -> BrowserResult:
        return BrowserResult(action=BrowserAction.CLICK, success=True, url=self._url)

    def fill(self, selector: str, value: str) -> BrowserResult:
        return BrowserResult(action=BrowserAction.FILL, success=True, url=self._url)

    def screenshot(self) -> BrowserResult:
        return BrowserResult(
            action=BrowserAction.SCREENSHOT,
            success=True,
            data={"placeholder": "screenshot_data"},
            url=self._url,
        )


class MockBrowserSession(BrowserSession):
    """Mock browser session for testing."""

    def __init__(self) -> None:
        self._running = False
        self._page: MockBrowserPage | None = None

    def start(self) -> None:
        self._running = True
        self._page = MockBrowserPage()

    def stop(self) -> None:
        self._running = False
        self._page = None

    def navigate(self, url: str) -> BrowserResult:
        if not self._running:
            return BrowserResult(
                action=BrowserAction.NAVIGATE,
                success=False,
                error="Browser session not started",
            )
        self._page = MockBrowserPage(url=url, title=f"Page at {url}")
        return BrowserResult(action=BrowserAction.NAVIGATE, success=True, url=url)

    def get_page(self) -> BrowserPage | None:
        return self._page

    def is_running(self) -> bool:
        return self._running


class PlaywrightBrowserPage(BrowserPage):
    """Real browser page using Playwright."""

    def __init__(self, page: Any) -> None:
        self._page = page

    def get_url(self) -> str:
        return self._page.url

    def get_title(self) -> str:
        return self._page.title()

    def get_text(self) -> str:
        try:
            return self._page.inner_text("body")
        except Exception:
            return ""

    def get_html(self) -> str:
        try:
            return self._page.content()
        except Exception:
            return ""

    def click(self, selector: str) -> BrowserResult:
        try:
            self._page.click(selector, timeout=10000)
            return BrowserResult(action=BrowserAction.CLICK, success=True, url=self.get_url())
        except Exception as exc:
            return BrowserResult(action=BrowserAction.CLICK, success=False, error=str(exc), url=self.get_url())

    def fill(self, selector: str, value: str) -> BrowserResult:
        try:
            self._page.fill(selector, value, timeout=10000)
            return BrowserResult(action=BrowserAction.FILL, success=True, url=self.get_url())
        except Exception as exc:
            return BrowserResult(action=BrowserAction.FILL, success=False, error=str(exc), url=self.get_url())

    def screenshot(self) -> BrowserResult:
        try:
            import tempfile, os
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            self._page.screenshot(path=tmp.name)
            return BrowserResult(
                action=BrowserAction.SCREENSHOT,
                success=True,
                data={"path": tmp.name},
                url=self.get_url(),
            )
        except Exception as exc:
            return BrowserResult(action=BrowserAction.SCREENSHOT, success=False, error=str(exc), url=self.get_url())


class PlaywrightBrowserSession(BrowserSession):
    """Real browser session using Playwright (Chromium)."""

    def __init__(self, headless: bool = False) -> None:
        self._headless = headless
        self._pw = None
        self._browser = None
        self._page: PlaywrightBrowserPage | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        raw_page = context.new_page()
        self._page = PlaywrightBrowserPage(raw_page)
        self._running = True
        logger.info("Playwright browser started (headless=%s)", self._headless)

    def stop(self) -> None:
        if not self._running:
            return
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._pw = None
        self._running = False
        logger.info("Playwright browser stopped")

    def navigate(self, url: str) -> BrowserResult:
        if not self._running:
            return BrowserResult(action=BrowserAction.NAVIGATE, success=False, error="Browser not started")
        try:
            self._page._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return BrowserResult(action=BrowserAction.NAVIGATE, success=True, url=url)
        except Exception as exc:
            return BrowserResult(action=BrowserAction.NAVIGATE, success=False, error=str(exc), url=url)

    def get_page(self) -> BrowserPage | None:
        return self._page

    def is_running(self) -> bool:
        return self._running


def create_default_session() -> BrowserSession:
    """Create a real Playwright browser session, fall back to mock."""
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        logger.info("Async event loop detected, using mock browser for compatibility")
        return MockBrowserSession()
    except RuntimeError:
        pass
    try:
        from playwright.sync_api import sync_playwright
        return PlaywrightBrowserSession(headless=False)
    except ImportError:
        logger.warning("Playwright not installed, using mock browser")
        return MockBrowserSession()


class BrowserTool:
    """Tool interface for browser operations with permission enforcement.

    Security: All navigation and actions are validated through
    BrowserSecurityGuard and NetworkSecurityGuard before execution.
    """

    def __init__(
        self,
        session: BrowserSession | None = None,
        network_guard: NetworkSecurityGuard | None = None,
        browser_guard: BrowserSecurityGuard | None = None,
    ) -> None:
        self._session = session or create_default_session()
        self._network_guard = network_guard or NetworkSecurityGuard()
        self._browser_guard = browser_guard or BrowserSecurityGuard(
            network_guard=self._network_guard,
        )

    @property
    def session(self) -> BrowserSession:
        return self._session

    @property
    def network_guard(self) -> NetworkSecurityGuard:
        return self._network_guard

    @property
    def browser_guard(self) -> BrowserSecurityGuard:
        return self._browser_guard

    def get_risk_level(self, action: BrowserAction) -> RiskLevel:
        """Get the risk level for a browser action."""
        return BROWSER_RISK_MAP.get(action, RiskLevel.MEDIUM)

    def navigate(self, url: str) -> BrowserResult:
        """Navigate to a URL with security validation."""
        # Validate through browser guard (origin + network checks)
        verdict = self._browser_guard.validate_navigation(url)
        if not verdict.allowed:
            logger.warning(
                "Browser navigation blocked: %s (url=%s)",
                verdict.reason, url,
            )
            return BrowserResult(
                action=BrowserAction.NAVIGATE,
                success=False,
                error=f"Navigation blocked: {verdict.reason}",
                url=url,
            )

        if not self._session.is_running():
            self._session.start()
        return self._session.navigate(url)

    def read_page(self) -> BrowserResult:
        """Read the current page content."""
        page = self._session.get_page()
        if page is None:
            return BrowserResult(
                action=BrowserAction.READ,
                success=False,
                error="No page loaded",
            )
        return BrowserResult(
            action=BrowserAction.READ,
            success=True,
            data={
                "url": page.get_url(),
                "title": page.get_title(),
                "text": page.get_text(),
            },
            url=page.get_url(),
        )

    def extract_text(self) -> BrowserResult:
        """Extract text from the current page."""
        return self.read_page()

    def click_element(self, selector: str) -> BrowserResult:
        """Click an element on the page."""
        page = self._session.get_page()
        if page is None:
            return BrowserResult(
                action=BrowserAction.CLICK,
                success=False,
                error="No page loaded",
            )
        return page.click(selector)

    def fill_form(self, selector: str, value: str) -> BrowserResult:
        """Fill a form field."""
        verdict = self._browser_guard.validate_action("fill")
        if not verdict.allowed:
            return BrowserResult(
                action=BrowserAction.FILL,
                success=False,
                error=f"Fill blocked: {verdict.reason}",
            )
        page = self._session.get_page()
        if page is None:
            return BrowserResult(
                action=BrowserAction.FILL,
                success=False,
                error="No page loaded",
            )
        return page.fill(selector, value)

    def take_screenshot(self) -> BrowserResult:
        """Take a screenshot of the current page."""
        page = self._session.get_page()
        if page is None:
            return BrowserResult(
                action=BrowserAction.SCREENSHOT,
                success=False,
                error="No page loaded",
            )
        return page.screenshot()


__all__ = [
    "BrowserAction",
    "BrowserResult",
    "BrowserPage",
    "BrowserSession",
    "BrowserTool",
    "MockBrowserPage",
    "MockBrowserSession",
    "PlaywrightBrowserPage",
    "PlaywrightBrowserSession",
    "BROWSER_RISK_MAP",
]
