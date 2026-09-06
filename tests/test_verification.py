"""Tests for the verification layer (ultron.verification)."""

from __future__ import annotations

from ultron.models import ExecutionResult, ExecutionStatus, VerificationStatus
from ultron.verification import Verifier


def test_verify_success():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="get_system_info",
        status=ExecutionStatus.SUCCESS,
        output={"os": "Windows", "cpu": "Intel"},
    )
    ver = verifier.verify(result)
    assert ver.status == VerificationStatus.PASSED
    assert all(ver.checks.values())
    assert "passed" in ver.message.lower()


def test_verify_failure_with_error():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="boom",
        status=ExecutionStatus.FAILED,
        error="RuntimeError: kaboom",
    )
    ver = verifier.verify(result)
    assert ver.status == VerificationStatus.FAILED
    assert not ver.checks["no_error"]


def test_verify_not_found():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="unknown",
        status=ExecutionStatus.NOT_FOUND,
        output={"error": "unknown tool: unknown"},
    )
    ver = verifier.verify(result)
    assert ver.status == VerificationStatus.FAILED
    assert not ver.checks["executed"]


def test_verify_output_structure():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="get_system_info",
        status=ExecutionStatus.SUCCESS,
        output={"os": "Windows", "cpu": "Intel", "ram_total_gb": 16},
    )
    ver = verifier.verify(result, expected_output_keys=["os", "cpu", "ram_total_gb"])
    assert ver.checks["valid_structure"] is True


def test_verify_output_structure_missing_keys():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="get_system_info",
        status=ExecutionStatus.SUCCESS,
        output={"os": "Windows"},
    )
    ver = verifier.verify(result, expected_output_keys=["os", "cpu", "ram_total_gb"])
    assert ver.checks["valid_structure"] is False
    assert ver.status == VerificationStatus.FAILED


def test_verify_permission_denied():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="create_file",
        status=ExecutionStatus.PERMISSION_DENIED,
        output={"error": "Denied for security testing"},
    )
    ver = verifier.verify(result)
    assert ver.status == VerificationStatus.FAILED


def test_verify_error_in_output_dict():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="read_file",
        status=ExecutionStatus.SUCCESS,
        output={"error": "file not found: /tmp/x"},
    )
    ver = verifier.verify(result)
    assert ver.checks["satisfies_request"] is False
    assert ver.status == VerificationStatus.FAILED


def test_verify_message_content():
    verifier = Verifier()
    result = ExecutionResult(
        tool_name="x",
        status=ExecutionStatus.FAILED,
        error="timeout",
    )
    ver = verifier.verify(result)
    assert "failed" in ver.message.lower()
    assert "no_error" in ver.message
