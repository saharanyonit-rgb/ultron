"""V1 URL tool: open a URL in the default browser.

Uses NetworkSecurityGuard for consistent URL validation across the system.
"""

from __future__ import annotations

from typing import Any, Dict

from ultron.network_security import NetworkSecurityGuard, NetworkPolicy
from ultron.tools._windows import ps_error, ps_ok, ps_quote, run_powershell
from ultron.tools.base import Tool

# Module-level guard for URL validation (shared across instances)
_default_guard = NetworkSecurityGuard()


class OpenUrl(Tool):
    name = "open_url"
    description = "Open a web URL in the default browser. Only http/https is allowed."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL, e.g. https://example.com."},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "opened": {"type": "string"},
        },
    }
    mutates = True

    def run(self, url: str = "", **kwargs: Any) -> Dict[str, Any]:
        target_url = url or kwargs.get("link") or kwargs.get("uri") or kwargs.get("target") or kwargs.get("url_address") or ""
        if not target_url:
            return {"error": "Missing 'url' parameter"}

        target_url = target_url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        # Use NetworkSecurityGuard for consistent validation
        verdict = _default_guard.validate_url(target_url)
        if not verdict.allowed:
            return {"error": f"URL blocked: {verdict.reason}"}

        proc = run_powershell(f"Start-Process {ps_quote(target_url)}", timeout=30)
        if not ps_ok(proc):
            return {"error": f"failed to open URL: {ps_error(proc)}"}
        return {"opened": target_url}
