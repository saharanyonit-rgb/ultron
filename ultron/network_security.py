"""Network and Browser Security for JARVIS Phase 5.

Network-level security controls: domain allowlisting, URL validation,
browser sandboxing, private-IP blocking, and network request interception.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger("ultron.network_security")


@dataclass
class NetworkPolicy:
    """Network access policy configuration."""
    allowed_domains: List[str] = field(default_factory=lambda: ["*"])
    blocked_domains: List[str] = field(default_factory=list)
    allowed_schemes: List[str] = field(default_factory=lambda: ["https"])
    max_request_size: int = 10 * 1024 * 1024
    require_https: bool = True
    block_private_ips: bool = True
    blocked_ip_ranges: List[str] = field(default_factory=lambda: [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_domains": self.allowed_domains,
            "blocked_domains": self.blocked_domains,
            "require_https": self.require_https,
            "block_private_ips": self.block_private_ips,
        }


@dataclass
class NetworkRequest:
    """Represents a network request for validation."""
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body_size: int = 0

    @property
    def domain(self) -> str:
        parsed = urlparse(self.url)
        return parsed.hostname or ""

    @property
    def scheme(self) -> str:
        return urlparse(self.url).scheme


@dataclass
class NetworkVerdict:
    """Result of network request validation."""
    allowed: bool = True
    reason: str = ""
    domain: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "domain": self.domain,
        }


class NetworkSecurityGuard:
    """Enforces network access policies.

    Validates URLs, checks domain allowlists/blocklists,
    and prevents access to private/internal networks.
    """

    def __init__(self, policy: Optional[NetworkPolicy] = None) -> None:
        self._policy = policy or NetworkPolicy()

    @property
    def policy(self) -> NetworkPolicy:
        return self._policy

    def validate_request(self, request: NetworkRequest) -> NetworkVerdict:
        """Validate a network request against the policy.

        Checks: scheme, HTTPS, blocked domains, allowlist, request size,
        and private-IP blocking via DNS resolution.
        """
        domain = request.domain

        if not domain:
            return NetworkVerdict(allowed=False, reason="Empty domain")

        if request.scheme not in self._policy.allowed_schemes:
            return NetworkVerdict(
                allowed=False,
                reason=f"Scheme '{request.scheme}' not allowed",
                domain=domain,
            )

        if self._policy.require_https and request.scheme != "https":
            return NetworkVerdict(
                allowed=False,
                reason="HTTPS required",
                domain=domain,
            )

        for blocked in self._policy.blocked_domains:
            if domain == blocked or domain.endswith("." + blocked):
                return NetworkVerdict(
                    allowed=False,
                    reason=f"Domain '{domain}' is blocked",
                    domain=domain,
                )

        if self._policy.allowed_domains != ["*"]:
            allowed = False
            for pattern in self._policy.allowed_domains:
                if domain == pattern or domain.endswith("." + pattern):
                    allowed = True
                    break
            if not allowed:
                return NetworkVerdict(
                    allowed=False,
                    reason=f"Domain '{domain}' not in allowlist",
                    domain=domain,
                )

        if request.body_size > self._policy.max_request_size:
            return NetworkVerdict(
                allowed=False,
                reason=f"Request size {request.body_size} exceeds limit",
                domain=domain,
            )

        # Private-IP blocking via DNS resolution
        if self._policy.block_private_ips:
            ip_check = self._check_private_ip(domain)
            if ip_check:
                return NetworkVerdict(
                    allowed=False,
                    reason=ip_check,
                    domain=domain,
                )

        return NetworkVerdict(allowed=True, domain=domain)

    def _check_private_ip(self, domain: str) -> Optional[str]:
        """Resolve domain and check if IP is private/blocked.

        Returns error message if blocked, None if allowed.
        """
        try:
            resolved = socket.getaddrinfo(domain, None, socket.AF_UNSPEC)
            for _, _, _, _, sockaddr in resolved:
                ip_str = sockaddr[0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    for blocked_range in self._policy.blocked_ip_ranges:
                        try:
                            network = ipaddress.ip_network(blocked_range, strict=False)
                            if ip in network:
                                return (
                                    f"Domain '{domain}' resolves to private/blocked IP "
                                    f"{ip_str} (in {blocked_range})"
                                )
                        except ValueError:
                            continue
                    # Also check is_private for ranges not explicitly listed
                    if ip.is_private:
                        return (
                            f"Domain '{domain}' resolves to private IP {ip_str}"
                        )
                except ValueError:
                    continue
        except (socket.gaierror, OSError) as exc:
            logger.debug("DNS resolution failed for %s: %s", domain, exc)
            # Fail open for DNS errors — the domain check already passed
        return None

    def validate_url(self, url: str) -> NetworkVerdict:
        """Convenience method to validate a URL string."""
        return self.validate_request(NetworkRequest(url=url))

    def sanitize_url(self, url: str) -> str:
        """Remove credentials from URL."""
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            sanitized = f"{parsed.scheme}://{parsed.hostname}"
            if parsed.port:
                sanitized += f":{parsed.port}"
            sanitized += parsed.path
            if parsed.query:
                sanitized += f"?{parsed.query}"
            return sanitized
        return url


@dataclass
class BrowserSandboxPolicy:
    """Browser sandbox configuration."""
    allowed_origins: List[str] = field(default_factory=list)
    block_download: bool = True
    block_javascript_dialogs: bool = True
    block_clipboard: bool = True
    max_pages: int = 10
    timeout_seconds: float = 30.0
    headless: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_origins": self.allowed_origins,
            "block_download": self.block_download,
            "block_javascript_dialogs": self.block_javascript_dialogs,
            "block_clipboard": self.block_clipboard,
            "max_pages": self.max_pages,
            "headless": self.headless,
        }


class BrowserSecurityGuard:
    """Enforces browser sandbox policies.

    Combines browser-specific origin checking with network-level
    security (scheme, domain, private-IP blocking).
    """

    def __init__(
        self,
        policy: Optional[BrowserSandboxPolicy] = None,
        network_guard: Optional[NetworkSecurityGuard] = None,
    ) -> None:
        self._policy = policy or BrowserSandboxPolicy()
        self._network_guard = network_guard or NetworkSecurityGuard()

    @property
    def policy(self) -> BrowserSandboxPolicy:
        return self._policy

    @property
    def network_guard(self) -> NetworkSecurityGuard:
        return self._network_guard

    def validate_navigation(self, url: str) -> NetworkVerdict:
        """Validate if navigation to URL is allowed.

        Checks browser origin policy AND network-level security.
        """
        domain = urlparse(url).hostname or ""

        # Browser-specific origin check
        if self._policy.allowed_origins:
            allowed = False
            for origin in self._policy.allowed_origins:
                if domain == origin or domain.endswith("." + origin):
                    allowed = True
                    break
            if not allowed:
                return NetworkVerdict(
                    allowed=False,
                    reason=f"Origin '{domain}' not in allowed origins",
                    domain=domain,
                )

        # Delegate to network guard for scheme/domain/IP checks
        return self._network_guard.validate_url(url)

    def validate_action(self, action: str, url: str = "") -> NetworkVerdict:
        """Validate a browser action against sandbox policy.

        Args:
            action: The action type (e.g., 'download', 'clipboard', 'navigate')
            url: Optional URL for navigation checks

        Returns:
            NetworkVerdict indicating if the action is allowed
        """
        action_lower = action.lower()

        if action_lower == "download" and self._policy.block_download:
            return NetworkVerdict(
                allowed=False,
                reason="Downloads are blocked by sandbox policy",
            )

        if action_lower == "clipboard" and self._policy.block_clipboard:
            return NetworkVerdict(
                allowed=False,
                reason="Clipboard access is blocked by sandbox policy",
            )

        if action_lower == "javascript_dialog" and self._policy.block_javascript_dialogs:
            return NetworkVerdict(
                allowed=False,
                reason="JavaScript dialogs are blocked by sandbox policy",
            )

        if url:
            return self.validate_navigation(url)

        return NetworkVerdict(allowed=True)


__all__ = [
    "NetworkPolicy",
    "NetworkRequest",
    "NetworkVerdict",
    "NetworkSecurityGuard",
    "BrowserSandboxPolicy",
    "BrowserSecurityGuard",
]
