"""Tests for the data models (ultron.models)."""

from __future__ import annotations

from ultron.models import (
    ExecutionResult,
    ExecutionStatus,
    ErrorResult,
    Plan,
    PlanStep,
    PlanStepStatus,
    RuntimeContext,
    VerificationResult,
    VerificationStatus,
)


def test_runtime_context_defaults():
    ctx = RuntimeContext()
    assert ctx.request_id
    assert ctx.conversation_id is None
    assert ctx.metadata == {}
    assert ctx.route_type is None


def test_runtime_context_custom():
    ctx = RuntimeContext(request_id="abc", conversation_id="sess1", metadata={"key": "val"})
    assert ctx.request_id == "abc"
    assert ctx.conversation_id == "sess1"
    assert ctx.metadata["key"] == "val"


def test_plan_step_defaults():
    step = PlanStep(tool_name="get_system_info")
    assert step.tool_name == "get_system_info"
    assert step.status == PlanStepStatus.PENDING
    assert step.result is None
    assert step.step_id


def test_plan_empty():
    plan = Plan()
    assert plan.is_empty
    assert plan.pending_steps() == []


def test_plan_with_steps():
    s1 = PlanStep(tool_name="read_file", arguments={"path": "/tmp/x"})
    s2 = PlanStep(tool_name="create_file", arguments={"path": "/tmp/y"})
    plan = Plan(steps=[s1, s2], description="read then write")
    assert not plan.is_empty
    assert len(plan.pending_steps()) == 2

    s1.status = PlanStepStatus.SUCCEEDED
    assert len(plan.pending_steps()) == 1
    assert plan.pending_steps()[0].tool_name == "create_file"


def test_execution_result_success():
    res = ExecutionResult(
        tool_name="get_system_info",
        status=ExecutionStatus.SUCCESS,
        output={"os": "Windows"},
    )
    assert res.status == ExecutionStatus.SUCCESS
    assert res.error is None


def test_execution_result_failure():
    res = ExecutionResult(
        tool_name="boom",
        status=ExecutionStatus.FAILED,
        error="RuntimeError: kaboom",
    )
    assert res.status == ExecutionStatus.FAILED
    assert "RuntimeError" in res.error


def test_verification_result_passed():
    exec_res = ExecutionResult(tool_name="x", status=ExecutionStatus.SUCCESS, output={"ok": True})
    ver = VerificationResult(
        execution_result=exec_res,
        status=VerificationStatus.PASSED,
        checks={"executed": True, "no_error": True},
    )
    assert ver.status == VerificationStatus.PASSED
    assert all(ver.checks.values())


def test_verification_result_failed():
    exec_res = ExecutionResult(tool_name="x", status=ExecutionStatus.FAILED, error="fail")
    ver = VerificationResult(
        execution_result=exec_res,
        status=VerificationStatus.FAILED,
        checks={"executed": True, "no_error": False},
        message="no_error check failed",
    )
    assert ver.status == VerificationStatus.FAILED


def test_error_result_from_exception():
    try:
        raise ValueError("bad value")
    except ValueError as e:
        err = ErrorResult.from_exception(e)
    assert err.error_type == "ValueError"
    assert err.message == "bad value"
    assert err.recoverable is True


def test_error_result_not_recoverable():
    err = ErrorResult(error_type="Fatal", message="crash", recoverable=False)
    assert not err.recoverable


def test_plan_step_status_values():
    assert PlanStepStatus.PENDING == "pending"
    assert PlanStepStatus.RUNNING == "running"
    assert PlanStepStatus.SUCCEEDED == "succeeded"
    assert PlanStepStatus.FAILED == "failed"
    assert PlanStepStatus.SKIPPED == "skipped"


def test_execution_status_values():
    assert ExecutionStatus.SUCCESS == "success"
    assert ExecutionStatus.FAILED == "failed"
    assert ExecutionStatus.NOT_FOUND == "not_found"
    assert ExecutionStatus.INVALID_INPUT == "invalid_input"
    assert ExecutionStatus.PERMISSION_DENIED == "permission_denied"
    assert ExecutionStatus.TIMEOUT == "timeout"
    assert ExecutionStatus.UNAVAILABLE == "unavailable"
