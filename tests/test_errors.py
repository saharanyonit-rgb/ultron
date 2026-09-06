"""Tests for the error hierarchy (ultron.errors)."""

from __future__ import annotations

import pytest

from ultron.errors import (
    AuthenticationError,
    ConfigurationError,
    ExecutionError,
    InvalidParametersError,
    InvalidToolError,
    JarvisError,
    MalformedResponseError,
    ProviderError,
    RateLimitError,
    PermissionDeniedError,
    TimeoutError,
    ToolAlreadyExistsError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    VerificationError,
)


def test_jarvis_error_is_base():
    assert issubclass(JarvisError, Exception)


def test_all_errors_extend_jarvis_error():
    error_classes = [
        ConfigurationError,
        ProviderError,
        AuthenticationError,
        RateLimitError,
        TimeoutError,
        MalformedResponseError,
        ToolError,
        ToolNotFoundError,
        ToolAlreadyExistsError,
        InvalidToolError,
        InvalidParametersError,
        PermissionDeniedError,
        ToolExecutionError,
        VerificationError,
        ExecutionError,
    ]
    for cls in error_classes:
        assert issubclass(cls, JarvisError), f"{cls.__name__} must extend JarvisError"


def test_provider_errors_extend_provider_error():
    for cls in (AuthenticationError, RateLimitError, TimeoutError, MalformedResponseError):
        assert issubclass(cls, ProviderError), f"{cls.__name__} must extend ProviderError"


def test_tool_errors_extend_tool_error():
    for cls in (ToolNotFoundError, ToolAlreadyExistsError, InvalidToolError,
                InvalidParametersError, PermissionDeniedError, ToolExecutionError):
        assert issubclass(cls, ToolError), f"{cls.__name__} must extend ToolError"


def test_error_messages():
    exc = ConfigurationError("missing API key")
    assert "missing API key" in str(exc)


def test_error_chaining():
    original = ValueError("root cause")
    try:
        raise ProviderError("provider failed") from original
    except ProviderError as wrapped:
        assert wrapped.__cause__ is original
