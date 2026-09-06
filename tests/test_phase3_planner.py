"""Tests for multi-step planner (ultron.planner)."""

from __future__ import annotations

from ultron.models import (
    ExecutionResult,
    ExecutionStatus,
    MultiStepPlan,
    MultiStepPlanStep,
    PlanStepPriority,
    PlanStepStatus,
)
from ultron.planner import Planner, PlanExecutor, PlanValidationError


def test_create_plan_success():
    planner = Planner()
    steps = [
        MultiStepPlanStep(tool_name="read_file", objective="read config"),
        MultiStepPlanStep(tool_name="create_file", objective="write output"),
    ]
    plan = planner.create_plan(steps, description="test plan")
    assert not plan.is_empty
    assert len(plan.steps) == 2
    assert plan.description == "test plan"


def test_create_plan_empty_steps():
    planner = Planner()
    try:
        planner.create_plan([])
        assert False, "Should raise PlanValidationError"
    except PlanValidationError as e:
        assert "at least one step" in str(e)


def test_create_plan_exceeds_max():
    planner = Planner(max_steps=2)
    steps = [MultiStepPlanStep(tool_name=f"tool_{i}") for i in range(5)]
    try:
        planner.create_plan(steps)
        assert False, "Should raise PlanValidationError"
    except PlanValidationError as e:
        assert "maximum is 2" in str(e)


def test_dependency_validation():
    planner = Planner()
    steps = [
        MultiStepPlanStep(step_id="a", tool_name="read_file", dependencies=["nonexistent"]),
    ]
    try:
        planner.create_plan(steps)
        assert False, "Should raise PlanValidationError"
    except PlanValidationError as e:
        assert "unknown step" in str(e)


def test_cycle_detection_simple():
    steps = [
        MultiStepPlanStep(step_id="a", dependencies=["b"]),
        MultiStepPlanStep(step_id="b", dependencies=["a"]),
    ]
    plan = MultiStepPlan(steps=steps)
    assert plan.has_cycle()


def test_cycle_detection_complex():
    steps = [
        MultiStepPlanStep(step_id="a", dependencies=["b"]),
        MultiStepPlanStep(step_id="b", dependencies=["c"]),
        MultiStepPlanStep(step_id="c", dependencies=["a"]),
    ]
    plan = MultiStepPlan(steps=steps)
    assert plan.has_cycle()


def test_ready_steps_after_dependency():
    step_b = MultiStepPlanStep(step_id="b", dependencies=["a"])
    step_a = MultiStepPlanStep(step_id="a")
    plan = MultiStepPlan(steps=[step_a, step_b])

    ready = plan.ready_steps()
    assert len(ready) == 1
    assert ready[0].step_id == "a"

    step_a.status = PlanStepStatus.SUCCEEDED
    ready = plan.ready_steps()
    assert len(ready) == 1
    assert ready[0].step_id == "b"


def test_execute_plan_success():
    def mock_executor(tool_name, args):
        return ExecutionResult(
            tool_name=tool_name,
            status=ExecutionStatus.SUCCESS,
            output={"result": "ok"},
        )

    executor = PlanExecutor(mock_executor)
    steps = [
        MultiStepPlanStep(tool_name="read_file", objective="read"),
        MultiStepPlanStep(tool_name="create_file", objective="write"),
    ]
    planner = Planner()
    plan = planner.create_plan(steps)

    result = executor.execute_plan(plan)
    assert len(result.completed_steps()) == 2


def test_execute_plan_with_failure():
    call_count = 0

    def mock_executor(tool_name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ExecutionResult(
                tool_name=tool_name,
                status=ExecutionStatus.FAILED,
                error="tool failed",
            )
        return ExecutionResult(
            tool_name=tool_name,
            status=ExecutionStatus.SUCCESS,
            output={"result": "ok"},
        )

    executor = PlanExecutor(mock_executor)
    steps = [MultiStepPlanStep(tool_name="failing_tool", objective="fail first")]
    planner = Planner()
    plan = planner.create_plan(steps)

    result = executor.execute_plan(plan)
    assert len(result.failed_steps()) == 1
    assert result.failed_steps()[0].retry_count == 1


def test_retry_on_failure():
    def mock_executor(tool_name, args):
        return ExecutionResult(
            tool_name=tool_name,
            status=ExecutionStatus.FAILED,
            error="always fails",
        )

    executor = PlanExecutor(mock_executor)
    step = MultiStepPlanStep(tool_name="failing_tool", objective="always fail", max_retries=2)
    planner = Planner()
    plan = planner.create_plan([step])

    result = executor.execute_plan(plan)
    assert result.failed_steps()[0].retry_count == 1
    assert result.failed_steps()[0].status == PlanStepStatus.FAILED


def test_multi_step_plan_properties():
    steps = [
        MultiStepPlanStep(step_id="a", status=PlanStepStatus.SUCCEEDED),
        MultiStepPlanStep(step_id="b", status=PlanStepStatus.FAILED),
        MultiStepPlanStep(step_id="c", status=PlanStepStatus.PENDING),
    ]
    plan = MultiStepPlan(steps=steps)

    assert len(plan.completed_steps()) == 1
    assert len(plan.failed_steps()) == 1
    assert len(plan.pending_steps()) == 1
    assert not plan.is_empty


def test_step_priority():
    step = MultiStepPlanStep(priority=PlanStepPriority.HIGH)
    assert step.priority == PlanStepPriority.HIGH
