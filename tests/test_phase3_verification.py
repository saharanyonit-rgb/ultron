"""Tests for semantic verification (ultron.verification.SemanticVerifier)."""

from __future__ import annotations

from ultron.models import ExecutionResult, ExecutionStatus, VerificationStatus
from ultron.verification import SemanticVerifier


def test_semantic_verify_success():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="get_system_info",
        status=ExecutionStatus.SUCCESS,
        output={"os": "Windows", "cpu": "Intel"},
    )
    ver = verifier.verify(result, objective="get system info")
    assert ver.status == VerificationStatus.PASSED
    assert all(ver.checks.values())


def test_semantic_verify_keyword_match():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="read_file",
        status=ExecutionStatus.SUCCESS,
        output={"content": "Python programming tutorial"},
    )
    ver = verifier.verify(
        result,
        objective="read file",
        expected_keywords=["python", "programming"],
    )
    assert ver.checks.get("semantic_keywords") is True
    assert ver.status == VerificationStatus.PASSED


def test_semantic_verify_keyword_miss():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="read_file",
        status=ExecutionStatus.SUCCESS,
        output={"content": "JavaScript tutorial"},
    )
    ver = verifier.verify(
        result,
        objective="read file",
        expected_keywords=["python", "programming"],
    )
    assert ver.checks.get("semantic_keywords") is False
    assert ver.status == VerificationStatus.FAILED


def test_semantic_verify_empty_output():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="tool",
        status=ExecutionStatus.SUCCESS,
        output={},
    )
    ver = verifier.verify(result, objective="do something")
    assert ver.checks.get("has_meaningful_output") is False
    assert ver.status == VerificationStatus.FAILED


def test_semantic_verify_structural_failure():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="tool",
        status=ExecutionStatus.FAILED,
        error="tool crashed",
    )
    ver = verifier.verify(result, objective="do something")
    assert ver.status == VerificationStatus.FAILED
    assert ver.checks.get("no_error") is False


def test_semantic_verify_no_keywords():
    verifier = SemanticVerifier()
    result = ExecutionResult(
        tool_name="tool",
        status=ExecutionStatus.SUCCESS,
        output={"result": "ok"},
    )
    ver = verifier.verify(result, objective="do something", expected_keywords=None)
    assert ver.checks.get("semantic_keywords") is True
