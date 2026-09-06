"""Tests for network security enforcement in browser operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ultron.browser import BrowserResult, BrowserTool, MockBrowserSession
from ultron.network_security import (
    BrowserSandboxPolicy,
    BrowserSecurityGuard,
    NetworkPolicy,
    NetworkSecurityGuard,
)
from ultron.tools.browser_tools import (
    ClickElement,
    FillFormField,
    NavigateUrl,
    ReadPage,
    TakeBrowserScreenshot,
    get_browser_tools,
)
from ultron.tools.urls import OpenUrl


# ═══════════════════════════════════════════════════════════════════
# NetworkSecurityGuard: Private-IP Blocking
# ═══════════════════════════════════════════════════════════════════

class TestPrivateIPBlocking:
    def test_localhost_blocked(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        verdict = guard.validate_url("https://127.0.0.1/admin")
        assert verdict.allowed is False
        assert "private" in verdict.reason.lower() or "blocked" in verdict.reason.lower()

    def test_private_ip_10_x_blocked(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        verdict = guard.validate_url("https://10.0.0.1/secret")
        assert verdict.allowed is False

    def test_private_ip_192_168_blocked(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        verdict = guard.validate_url("https://192.168.1.1/admin")
        assert verdict.allowed is False

    def test_private_ip_172_16_blocked(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        verdict = guard.validate_url("https://172.16.0.1/admin")
        assert verdict.allowed is False

    def test_public_ip_allowed(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        # google.com resolves to public IPs
        verdict = guard.validate_url("https://www.google.com")
        assert verdict.allowed is True

    def test_block_private_ips_disabled(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=False))
        verdict = guard.validate_url("https://127.0.0.1/admin")
        # Should pass IP check (but may fail other checks)
        assert "private" not in verdict.reason.lower()

    def test_dns_resolution_failure_fails_open(self):
        guard = NetworkSecurityGuard(NetworkPolicy(block_private_ips=True))
        # Nonexistent domain - DNS fails, should fail open
        verdict = guard.validate_url("https://this-domain-does-not-exist-12345.com")
        assert verdict.allowed is True  # DNS error = fail open


# ═══════════════════════════════════════════════════════════════════
# BrowserSecurityGuard: Combined Checks
# ═══════════════════════════════════════════════════════════════════

class TestBrowserSecurityGuard:
    def test_origin_check_plus_network_check(self):
        guard = BrowserSecurityGuard(
            policy=BrowserSandboxPolicy(allowed_origins=["example.com"]),
            network_guard=NetworkSecurityGuard(NetworkPolicy(require_https=True)),
        )
        # Allowed origin, HTTPS
        assert guard.validate_navigation("https://example.com").allowed is True
        # Blocked origin
        assert guard.validate_navigation("https://evil.com").allowed is False
        # HTTP blocked by network guard
        assert guard.validate_navigation("http://example.com").allowed is False

    def test_download_blocked(self):
        guard = BrowserSecurityGuard(BrowserSandboxPolicy(block_download=True))
        verdict = guard.validate_action("download")
        assert verdict.allowed is False
        assert "download" in verdict.reason.lower()

    def test_clipboard_blocked(self):
        guard = BrowserSecurityGuard(BrowserSandboxPolicy(block_clipboard=True))
        verdict = guard.validate_action("clipboard")
        assert verdict.allowed is False
        assert "clipboard" in verdict.reason.lower()

    def test_javascript_dialog_blocked(self):
        guard = BrowserSecurityGuard(BrowserSandboxPolicy(block_javascript_dialogs=True))
        verdict = guard.validate_action("javascript_dialog")
        assert verdict.allowed is False

    def test_unknown_action_allowed(self):
        guard = BrowserSecurityGuard()
        verdict = guard.validate_action("scroll")
        assert verdict.allowed is True


# ═══════════════════════════════════════════════════════════════════
# BrowserTool: Security Integration
# ═══════════════════════════════════════════════════════════════════

class TestBrowserToolSecurity:
    def test_navigate_blocked_by_network_guard(self):
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        browser_guard = BrowserSecurityGuard(network_guard=guard)
        bt = BrowserTool(
            session=MockBrowserSession(),
            network_guard=guard,
            browser_guard=browser_guard,
        )
        result = bt.navigate("http://example.com")
        assert result.success is False
        assert "blocked" in result.error.lower()

    def test_navigate_allowed(self):
        bt = BrowserTool()
        result = bt.navigate("https://example.com")
        assert result.success is True

    def test_navigate_blocked_by_origin(self):
        guard = NetworkSecurityGuard()
        browser_guard = BrowserSecurityGuard(
            policy=BrowserSandboxPolicy(allowed_origins=["allowed.com"]),
            network_guard=guard,
        )
        bt = BrowserTool(
            session=MockBrowserSession(),
            browser_guard=browser_guard,
        )
        result = bt.navigate("https://evil.com")
        assert result.success is False
        assert "origin" in result.error.lower()

    def test_fill_form_works(self):
        guard = NetworkSecurityGuard()
        browser_guard = BrowserSecurityGuard(
            policy=BrowserSandboxPolicy(block_clipboard=True),
            network_guard=guard,
        )
        bt = BrowserTool(
            session=MockBrowserSession(),
            browser_guard=browser_guard,
        )
        bt.navigate("https://example.com")
        result = bt.fill_form("input", "value")
        # Fill is allowed (only clipboard is blocked)
        assert result.success is True

    def test_security_guards_accessible(self):
        bt = BrowserTool()
        assert bt.network_guard is not None
        assert bt.browser_guard is not None


# ═══════════════════════════════════════════════════════════════════
# Browser Tools in Registry
# ═══════════════════════════════════════════════════════════════════

class TestBrowserToolRegistration:
    def test_all_browser_tools_registered(self):
        tools = get_browser_tools()
        names = [t.name for t in tools]
        assert "navigate_url" in names
        assert "read_page" in names
        assert "click_element" in names
        assert "fill_form" in names
        assert "browser_screenshot" in names

    def test_navigate_url_tool_validates(self):
        tools = get_browser_tools()
        nav = [t for t in tools if t.name == "navigate_url"][0]
        result = nav.run(url="http://127.0.0.1/admin")
        # Should be blocked by network guard
        assert result.get("success") is False or "blocked" in str(result).lower() or "error" in result

    def test_open_url_uses_network_guard(self):
        tool = OpenUrl()
        result = tool.run(url="http://127.0.0.1/admin")
        assert "error" in result
        assert "blocked" in result["error"].lower() or "private" in result["error"].lower()

    def test_open_url_allows_valid(self):
        tool = OpenUrl()
        # This should pass validation (may fail at actual open)
        result = tool.run(url="https://example.com")
        # Either opened successfully or failed at OS level, not validation
        assert "blocked" not in str(result).lower()


# ═══════════════════════════════════════════════════════════════════
# NetworkSecurityGuard: Existing Checks Still Work
# ═══════════════════════════════════════════════════════════════════

class TestExistingNetworkChecks:
    def test_https_required(self):
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        assert guard.validate_url("https://example.com").allowed is True
        assert guard.validate_url("http://example.com").allowed is False

    def test_blocked_domain(self):
        guard = NetworkSecurityGuard(NetworkPolicy(blocked_domains=["evil.com"]))
        assert guard.validate_url("https://evil.com").allowed is False
        assert guard.validate_url("https://sub.evil.com").allowed is False
        assert guard.validate_url("https://good.com").allowed is True

    def test_allowlist(self):
        guard = NetworkSecurityGuard(NetworkPolicy(allowed_domains=["ok.com"]))
        assert guard.validate_url("https://ok.com").allowed is True
        assert guard.validate_url("https://other.com").allowed is False

    def test_sanitize_url(self):
        guard = NetworkSecurityGuard()
        clean = guard.sanitize_url("https://user:pass@example.com/path")
        assert "user" not in clean
        assert "pass" not in clean
