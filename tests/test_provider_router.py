"""Tests for multi-provider routing (ultron.llm.router)."""

from __future__ import annotations

from typing import List, Optional

import pytest

from ultron.errors import AuthenticationError, ProviderError, TimeoutError
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.llm.router import ProviderRouter


class WorkingProvider(LLMProvider):
    name = "working"

    def __init__(self, response: str = "working response"):
        self._response = response
        self.call_count = 0

    def complete(self, text, tools):
        self.call_count += 1
        return ProviderResult(text=self._response, tool_calls=[])

    def feed_tool_results(self, results):
        pass

    def health_check(self):
        return True


class FailingProvider(LLMProvider):
    name = "failing"

    def __init__(self, error: Exception = None):
        self._error = error or ProviderError("generic failure")
        self.call_count = 0

    def complete(self, text, tools):
        self.call_count += 1
        raise self._error

    def feed_tool_results(self, results):
        pass

    def health_check(self):
        return False


def test_router_uses_first_provider():
    p1 = WorkingProvider("response from p1")
    p2 = WorkingProvider("response from p2")
    router = ProviderRouter(providers=[p1, p2])

    result = router.complete("hello", [])
    assert result.text == "response from p1"
    assert p1.call_count == 1
    assert p2.call_count == 0


def test_router_falls_back_on_failure():
    p1 = FailingProvider(ProviderError("p1 failed"))
    p2 = WorkingProvider("response from p2")
    router = ProviderRouter(providers=[p1, p2])

    result = router.complete("hello", [])
    assert result.text == "response from p2"
    assert p1.call_count == 1
    assert p2.call_count == 1


def test_router_tries_all_providers():
    p1 = FailingProvider(ProviderError("p1 failed"))
    p2 = FailingProvider(TimeoutError("p2 timeout"))
    p3 = WorkingProvider("response from p3")
    router = ProviderRouter(providers=[p1, p2, p3])

    result = router.complete("hello", [])
    assert result.text == "response from p3"
    assert p1.call_count == 1
    assert p2.call_count == 1
    assert p3.call_count == 1


def test_router_raises_when_all_fail():
    p1 = FailingProvider(AuthenticationError("auth failed"))
    p2 = FailingProvider(TimeoutError("timeout"))
    router = ProviderRouter(providers=[p1, p2])

    with pytest.raises(TimeoutError):
        router.complete("hello", [])


def test_router_empty_providers_raises():
    with pytest.raises(ValueError, match="at least one"):
        ProviderRouter(providers=[])


def test_router_tracks_active_provider():
    p1 = FailingProvider(ProviderError("fail"))
    p2 = WorkingProvider("ok")
    router = ProviderRouter(providers=[p1, p2])

    assert router.active_provider is p1
    router.complete("hello", [])
    assert router.active_provider is p2


def test_router_health_check():
    p1 = WorkingProvider()
    assert ProviderRouter(providers=[p1]).health_check() is True

    p2 = FailingProvider()
    # health_check catches exceptions, returns False if all fail
    assert ProviderRouter(providers=[p2]).health_check() is False


def test_router_health_check_mixed():
    p1 = FailingProvider()
    p2 = WorkingProvider()
    assert ProviderRouter(providers=[p1, p2]).health_check() is True


def test_router_feed_tool_results():
    p1 = WorkingProvider()
    router = ProviderRouter(providers=[p1])

    # Should not raise
    router.feed_tool_results([])


def test_router_reset():
    p1 = FailingProvider(ProviderError("fail"))
    p2 = WorkingProvider("ok")
    router = ProviderRouter(providers=[p1, p2])

    router.complete("hello", [])
    assert router.active_provider is p2

    router.reset()
    assert router.active_provider is p1


def test_router_providers_list():
    p1 = WorkingProvider("a")
    p2 = WorkingProvider("b")
    router = ProviderRouter(providers=[p1, p2])
    assert len(router.providers) == 2
    assert router.providers[0] is p1
    assert router.providers[1] is p2


def test_router_name():
    router = ProviderRouter(providers=[WorkingProvider()])
    assert router.name == "provider_router"
