"""Structured error hierarchy for JARVIS / Ultron.

Every error the system can raise or return extends JarvisError so callers
can catch broadly or granularly.  Errors carry diagnostic information but
never expose secrets (API keys, tokens, passwords).
"""

from __future__ import annotations


class JarvisError(Exception):
    """Base exception for all JARVIS errors."""


# ── Configuration ──────────────────────────────────────────────────

class ConfigurationError(JarvisError):
    """Raised when the environment is unusable (missing key, bad value, etc.)."""


# ── Provider / LLM ────────────────────────────────────────────────

class ProviderError(JarvisError):
    """Base for all LLM-provider errors."""


class AuthenticationError(ProviderError):
    """Raised when the provider rejects the API key or token."""


class RateLimitError(ProviderError):
    """Raised when the provider returns a rate-limit / 429 response."""


class TimeoutError(ProviderError):
    """Raised when a provider request exceeds its time budget."""


class MalformedResponseError(ProviderError):
    """Raised when the provider returns data that cannot be parsed."""


class QuotaError(ProviderError):
    """Raised when the provider's daily or periodic quota is exhausted."""


class ProviderUnavailableError(ProviderError):
    """Raised when the provider is temporarily unavailable."""


class ProviderBusyError(ProviderError):
    """Raised when the provider is busy and cannot accept requests."""


class ProviderNetworkError(ProviderError):
    """Raised when there is a network connectivity issue with the provider."""


class ProviderServerError(ProviderError):
    """Raised when the provider returns a server error (5xx)."""


# ── Verification ───────────────────────────────────────────────────

class VerificationError(JarvisError):
    """Raised when verification of a tool result fails."""


# ── Pipeline / Execution ───────────────────────────────────────────

class ExecutionError(JarvisError):
    """Raised when the pipeline or agent loop encounters a fatal execution fault."""


# ── Tool ───────────────────────────────────────────────────────────

class ToolError(JarvisError):
    """Base for all tool-related errors."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not in the registry."""


class ToolAlreadyExistsError(ToolError):
    """Raised when registering a tool whose name is already registered."""


class InvalidToolError(ToolError):
    """Raised when a tool definition is invalid."""


class InvalidParametersError(ToolError):
    """Raised when tool parameters fail validation."""


class PermissionDeniedError(ToolError):
    """Raised when tool execution is denied by security permissions."""


class ToolExecutionError(ToolError):
    """Raised when a tool's run() method fails internally."""


# ── Recovery ───────────────────────────────────────────────────────

class RecoveryError(JarvisError):
    """Raised when recovery/replanning fails."""


__all__ = [
    "JarvisError",
    "ConfigurationError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "MalformedResponseError",
    "QuotaError",
    "ProviderUnavailableError",
    "ProviderBusyError",
    "ProviderNetworkError",
    "ProviderServerError",
    "ToolError",
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "InvalidToolError",
    "InvalidParametersError",
    "PermissionDeniedError",
    "ToolExecutionError",
    "VerificationError",
    "ExecutionError",
    "RecoveryError",
]
