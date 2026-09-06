"""Tests for recovery and replanning (Phase 4)."""

from __future__ import annotations

from ultron.execution_state import StepState, TaskState, TaskStatus
from ultron.recovery import (
    RecoveryAction,
    RecoveryEngine,
    ErrorClass,
)


def test_classify_error_transient():
    engine = RecoveryEngine()
    assert engine.classify_error(TimeoutError("timeout")) == ErrorClass.TRANSIENT


def test_classify_error_permanent():
    engine = RecoveryEngine()
    assert engine.classify_error(FileNotFoundError("not found")) == ErrorClass.PERMANENT


def test_classify_error_recoverable():
    engine = RecoveryEngine()
    assert engine.classify_error(RuntimeError("tool failed")) == ErrorClass.RECOVERABLE


def test_decide_recovery_retry():
    engine = RecoveryEngine(max_retries=3)
    step = StepState(step_id="s1", retry_count=0)
    decision = engine.decide_recovery(step, TimeoutError("timeout"))
    assert decision.action == RecoveryAction.RETRY


def test_decide_recovery_abort_on_max_retries():
    engine = RecoveryEngine(max_retries=2)
    step = StepState(step_id="s1", retry_count=2)
    decision = engine.decide_recovery(step, TimeoutError("timeout"))
    assert decision.action == RecoveryAction.ABORT


def test_decide_recovery_skip_on_permanent():
    engine = RecoveryEngine()
    step = StepState(step_id="s1", retry_count=0)
    decision = engine.decide_recovery(step, FileNotFoundError("missing"))
    assert decision.action == RecoveryAction.SKIP


def test_should_retry():
    engine = RecoveryEngine(max_retries=3)
    step = StepState(step_id="s1", retry_count=0)
    assert engine.should_retry(step, TimeoutError("timeout")) is True


def test_should_not_retry_at_limit():
    engine = RecoveryEngine(max_retries=2)
    step = StepState(step_id="s1", retry_count=2)
    assert engine.should_retry(step, TimeoutError("timeout")) is False


def test_execute_recovery_retry():
    engine = RecoveryEngine(max_retries=3)
    task = TaskState(task_id="t1")
    step = StepState(step_id="s1", retry_count=0, status="failed")
    task.steps = [step]

    result = engine.execute_recovery(task, step, TimeoutError("timeout"))
    assert result is not None
    assert step.retry_count == 1
    assert step.status == "pending"


def test_execute_recovery_abort():
    engine = RecoveryEngine(max_retries=1)
    task = TaskState(task_id="t1")
    step = StepState(step_id="s1", retry_count=1, status="failed")
    task.steps = [step]

    result = engine.execute_recovery(task, step, TimeoutError("timeout"))
    assert result is not None
    assert task.status == TaskStatus.FAILED


def test_execute_recovery_skip():
    engine = RecoveryEngine()
    task = TaskState(task_id="t1")
    step = StepState(step_id="s1", retry_count=0, status="failed")
    task.steps = [step]

    result = engine.execute_recovery(task, step, FileNotFoundError("missing"))
    assert result is not None
    assert step.status == "skipped"


def test_recovery_decisions_recorded():
    engine = RecoveryEngine()
    step = StepState(step_id="s1", retry_count=0)
    engine.decide_recovery(step, TimeoutError("timeout"))
    engine.decide_recovery(step, FileNotFoundError("missing"))
    assert len(engine.decisions) == 2


def test_error_class_map_keys():
    from ultron.recovery import ERROR_CLASS_MAP
    assert "TimeoutError" in ERROR_CLASS_MAP
    assert "FileNotFoundError" in ERROR_CLASS_MAP
    assert "RuntimeError" in ERROR_CLASS_MAP
