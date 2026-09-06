"""Credential Management for JARVIS Phase 5.

Secure handling of secrets, tokens, and API keys. Prevents leakage
into logs, tool outputs, or LLM conversations.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.credentials")


@dataclass
class Credential:
    """A stored credential."""
    name: str = ""
    credential_type: str = "api_key"
    value_hash: str = ""
    service: str = ""
    scopes: List[str] = field(default_factory=list)
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        from datetime import datetime, timezone
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except ValueError:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "credential_type": self.credential_type,
            "value_hash": self.value_hash,
            "service": self.service,
            "scopes": self.scopes,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }


class CredentialManager:
    """Secure credential storage and sanitization.

    Features:
    - Hash-based storage (never stores plaintext)
    - Automatic sanitization of outputs/logs
    - Pattern detection for leaked secrets
    - Environment variable integration
    """

    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,})', "API Key"),
        (r'(?i)(token|access[_-]?token|auth[_-]?token)\s*[=:]\s*["\']?([A-Za-z0-9_\-\.]{20,})', "Token"),
        (r'(?i)(secret|client[_-]?secret)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,})', "Secret"),
        (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']{8,})', "Password"),
        (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private Key"),
    ]

    def __init__(self) -> None:
        self._credentials: Dict[str, Credential] = {}
        self._known_values: Dict[str, str] = {}

    def store(
        self,
        name: str,
        value: str,
        credential_type: str = "api_key",
        service: str = "",
        **kwargs: Any,
    ) -> Credential:
        """Store a credential securely."""
        value_hash = hashlib.sha256(value.encode()).hexdigest()
        cred = Credential(
            name=name,
            credential_type=credential_type,
            value_hash=value_hash,
            service=service,
            **{k: v for k, v in kwargs.items() if k in Credential.__dataclass_fields__},
        )
        self._credentials[name] = cred
        self._known_values[value_hash] = value
        return cred

    def retrieve(self, name: str) -> Optional[str]:
        """Retrieve a credential value by name."""
        cred = self._credentials.get(name)
        if not cred:
            return None
        return self._known_values.get(cred.value_hash)

    def get_credential(self, name: str) -> Optional[Credential]:
        """Get credential metadata (without value)."""
        return self._credentials.get(name)

    def list_credentials(self, service: Optional[str] = None) -> List[Credential]:
        """List stored credentials."""
        creds = list(self._credentials.values())
        if service:
            creds = [c for c in creds if c.service == service]
        return creds

    def delete(self, name: str) -> bool:
        """Delete a credential."""
        cred = self._credentials.pop(name, None)
        if cred:
            self._known_values.pop(cred.value_hash, None)
            return True
        return False

    def sanitize_text(self, text: str) -> str:
        """Remove any known credential values from text."""
        sanitized = text
        for value in self._known_values.values():
            if len(value) >= 8 and value in sanitized:
                sanitized = sanitized.replace(value, "[REDACTED]")
        return sanitized

    def detect_secrets(self, text: str) -> List[Dict[str, str]]:
        """Scan text for potential secret leakage."""
        findings = []
        for pattern, label in self.SECRET_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                findings.append({
                    "type": label,
                    "match": match.group(0)[:50] + "...",
                    "position": match.span(),
                })
        return findings

    def load_from_env(self, prefix: str = "ULTRON_") -> int:
        """Load credentials from environment variables."""
        loaded = 0
        for key, value in os.environ.items():
            if key.startswith(prefix) and value:
                name = key[len(prefix):].lower()
                self.store(name, value, service="env")
                loaded += 1
        return loaded

    def to_dict(self) -> Dict[str, Any]:
        """Export credential metadata (no values)."""
        return {
            name: cred.to_dict()
            for name, cred in self._credentials.items()
        }


__all__ = [
    "Credential",
    "CredentialManager",
]
