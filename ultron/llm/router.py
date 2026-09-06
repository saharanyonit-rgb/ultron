"""Multi-provider model routing with automatic fallback.

Wraps multiple LLMProvider instances and tries them in order.  If the
primary provider fails (auth, timeout, provider error, quota exhaustion),
the next provider in the fallback chain is attempted.

Implements LLMProvider so it can be used anywhere a single provider is
expected — no changes to the Agent or Brain required.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ultron.errors import (
    AuthenticationError,
    ProviderError,
    QuotaError,
    RateLimitError,
    TimeoutError,
    MalformedResponseError,
    ProviderUnavailableError,
)
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if False:  # TYPE_CHECKING
    from ultron.tools.base import ToolSpec

logger = logging.getLogger("ultron.llm.router")


class ProviderRouter(LLMProvider):
    """Wraps multiple providers with automatic fallback.

    Usage:
        router = ProviderRouter(providers=[primary, fallback1, fallback2])
        result = router.complete(text, tools)

    If primary.complete() raises an error, the appropriate classification
    determines whether to retry, fallback, or abort.

    Phase 7.8: Enhanced with quota detection, health tracking, and
    structured failover decisions.
    """

    name = "provider_router"

    def __init__(self, providers: List[LLMProvider]) -> None:
        if not providers:
            raise ValueError("ProviderRouter requires at least one provider")
        self._providers = list(providers)
        self._active_index = 0
        self._failed_providers: dict[str, float] = {}  # provider_name -> retry_after_timestamp
        self._max_fallback_depth = 3

    @property
    def active_provider(self) -> LLMProvider:
        """The currently active provider."""
        return self._providers[self._active_index]

    @property
    def providers(self) -> List[LLMProvider]:
        """All providers in fallback order."""
        return list(self._providers)

    def _should_skip_provider(self, provider_name: str) -> bool:
        """Check if a provider is in cooldown (recently failed)."""
        if provider_name in self._failed_providers:
            retry_after = self._failed_providers[provider_name]
            if retry_after > __import__("time").time():
                return True
            # Provider cooldown expired, remove from tracking
            del self._failed_providers[provider_name]
        return False

    def _mark_provider_failed(self, provider_name: str, retry_after: float) -> None:
        """Mark a provider as failed with a retry timestamp."""
        self._failed_providers[provider_name] = retry_after
        # Keep only recent failures
        if len(self._failed_providers) > self._max_fallback_depth * 2:
            current_time = __import__("time").time()
            self._failed_providers = {
                k: v for k, v in self._failed_providers.items() if v > current_time
            }

    def _classify_error(self, exc: Exception) -> str:
        """Classify the error to determine routing behavior."""
        exc_type = type(exc).__name__

        if isinstance(exc, QuotaError):
            return "quota_exhausted"

        if isinstance(exc, RateLimitError):
            return "rate_limited"

        if isinstance(exc, AuthenticationError):
            return "authentication_failed"

        if isinstance(exc, TimeoutError):
            return "timeout"

        if isinstance(exc, MalformedResponseError):
            return "malformed_response"

        if isinstance(exc, ProviderUnavailableError):
            return "unavailable"

        if isinstance(exc, ProviderError):
            return "provider_error"

        return "unknown"

    def _is_retryable(self, classification: str) -> bool:
        """Determine if the error classification allows retrying the same provider."""
        return classification in ("rate_limited", "timeout", "provider_error", "unknown")

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        """Try each provider in order until one succeeds or all fail."""
        last_error: Optional[Exception] = None
        fallback_triggered = False
        fallback_provider_index: Optional[int] = None

        for i, provider in enumerate(self._providers):
            # Skip providers in cooldown
            if self._should_skip_provider(provider.name):
                logger.debug("Skipping provider %s (in cooldown)", provider.name)
                continue

            try:
                logger.debug("Trying provider: %s (index %d)", provider.name, i)
                result = provider.complete(text, tools)
                if i != self._active_index:
                    logger.info("Provider %s succeeded after earlier failures", provider.name)
                    self._active_index = i
                return result

            except (QuotaError, RateLimitError, AuthenticationError, TimeoutError,
                    ProviderError, MalformedResponseError, ProviderUnavailableError) as exc:

                last_error = exc
                classification = self._classify_error(exc)
                logger.warning(
                    "Provider %s failed (%s: %s), classification: %s",
                    provider.name,
                    classification,
                    exc,
                    classification,
                )

                # Handle quota exhaustion - skip this provider and trigger fallback
                if classification == "quota_exhausted":
                    retry_after = self._extract_retry_after(exc)
                    self._mark_provider_failed(provider.name, retry_after)
                    fallback_triggered = True
                    fallback_provider_index = i
                    logger.info("Quota exhausted for %s, will fallback", provider.name)
                    # Don't continue the loop - go directly to fallback
                    break

                # Handle rate limiting - may retry same provider or move to next
                if classification == "rate_limited":
                    # Try same provider once more with backoff, or move to next
                    if self._is_retryable(classification):
                        # Could add sleep here, but for now move to next
                        pass
                    # Continue to next provider
                    continue

                # Handle authentication - never retry same provider
                if classification == "authentication_failed":
                    # Skip this provider permanently
                    self._mark_provider_failed(provider.name, 0)
                    continue

                # Handle timeout - may retry or move on
                if classification == "timeout":
                    # Continue to next provider
                    continue

                # Handle unavailable - skip temporarily
                if classification == "unavailable":
                    self._mark_provider_failed(provider.name, __import__("time").time() + 60)
                    continue

                # Handle malformed response - try once, then move on
                if classification == "malformed_response":
                    continue

                # Generic provider error - move to next
                if classification == "provider_error":
                    continue

                # Unknown - move to next
                continue

        # If quota was exhausted, attempt fallback
        if fallback_triggered and fallback_provider_index is not None:
            logger.info("Attempting fallback due to quota exhaustion")
            # Try fallback providers
            for i in range(fallback_provider_index + 1, len(self._providers)):
                provider = self._providers[i]
                if self._should_skip_provider(provider.name):
                    logger.debug("Skipping fallback provider %s (in cooldown)", provider.name)
                    continue
                try:
                    logger.info("Trying fallback provider: %s", provider.name)
                    result = provider.complete(text, tools)
                    self._active_index = i
                    logger.info("Fallback provider %s succeeded", provider.name)
                    return result
                except Exception as fallback_exc:
                    logger.warning("Fallback provider %s also failed: %s", provider.name, fallback_exc)
                    continue

        # All providers failed
        if last_error:
            raise last_error
        return ProviderResult(text="All providers failed.", tool_calls=[])

    def _extract_retry_after(self, exc: QuotaError) -> float:
        """Extract retry_after from quota error if available."""
        # Try to get retry delay from the exception
        if hasattr(exc, "retry_after") and exc.retry_after:
            return __import__("time").time() + exc.retry_after

        # Try to parse from error message
        msg = str(exc).lower()
        import re
        match = re.search(r'retry after[\s:]+(\d+)', msg)
        if match:
            retry_seconds = int(match.group(1))
            return __import__("time").time() + retry_seconds

        # Default: mark as unavailable for 1 hour
        return __import__("time").time() + 3600

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        """Feed tool results to the active provider."""
        self._providers[self._active_index].feed_tool_results(results)

    def health_check(self) -> bool:
        """Check if at least one provider is healthy and not in cooldown."""
        current_time = __import__("time").time()
        for provider in self._providers:
            if not self._should_skip_provider(provider.name):
                try:
                    if provider.health_check():
                        return True
                except Exception:
                    continue
        return False

    def reset(self) -> None:
        """Reset to the first provider in the chain and clear failure tracking."""
        self._active_index = 0
        self._failed_providers = {}


__all__ = ["ProviderRouter"]
