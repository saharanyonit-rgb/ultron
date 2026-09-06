"""Tests for streaming execution status (Phase 4)."""

from __future__ import annotations

from ultron.status import (
    StatusEvent,
    StatusReporter,
    StatusUpdate,
    CallbackSubscriber,
)


def test_status_reporter_report():
    reporter = StatusReporter()
    reporter.report(StatusEvent.TASK_STARTED, "task started", task_id="t1")
    assert len(reporter.history) == 1
    assert reporter.history[0].event == StatusEvent.TASK_STARTED


def test_status_reporter_subscriber():
    reporter = StatusReporter()
    updates = []
    subscriber = CallbackSubscriber(lambda u: updates.append(u))
    reporter.subscribe(subscriber)

    reporter.report(StatusEvent.PLANNING, task_id="t1")
    assert len(updates) == 1
    assert updates[0].event == StatusEvent.PLANNING


def test_status_reporter_unsubscribe():
    reporter = StatusReporter()
    updates = []
    subscriber = CallbackSubscriber(lambda u: updates.append(u))
    reporter.subscribe(subscriber)
    reporter.unsubscribe(subscriber)

    reporter.report(StatusEvent.COMPLETED, task_id="t1")
    assert len(updates) == 0


def test_status_reporter_task_started():
    reporter = StatusReporter()
    reporter.task_started("t1", "test task")
    assert len(reporter.history) == 1
    assert reporter.history[0].task_id == "t1"


def test_status_reporter_planning():
    reporter = StatusReporter()
    reporter.planning("t1")
    assert reporter.history[0].event == StatusEvent.PLANNING


def test_status_reporter_plan_created():
    reporter = StatusReporter()
    reporter.plan_created("t1", 5)
    assert "5" in reporter.history[0].message


def test_status_reporter_agent_selected():
    reporter = StatusReporter()
    reporter.agent_selected("t1", "research")
    assert "research" in reporter.history[0].message


def test_status_reporter_step_started():
    reporter = StatusReporter()
    reporter.step_started("t1", "s1", "read file", 0.25)
    assert reporter.history[0].progress == 0.25


def test_status_reporter_step_completed():
    reporter = StatusReporter()
    reporter.step_completed("t1", "s1", 0.5)
    assert reporter.history[0].progress == 0.5


def test_status_reporter_step_failed():
    reporter = StatusReporter()
    reporter.step_failed("t1", "s1", "timeout")
    assert "timeout" in reporter.history[0].metadata["error"]


def test_status_reporter_completed():
    reporter = StatusReporter()
    reporter.completed("t1")
    assert reporter.history[0].progress == 1.0


def test_status_reporter_failed():
    reporter = StatusReporter()
    reporter.failed("t1", "error")
    assert "error" in reporter.history[0].message


def test_status_update_to_dict():
    update = StatusUpdate(
        event=StatusEvent.STEP_STARTED,
        message="test",
        task_id="t1",
        step_id="s1",
        progress=0.5,
    )
    d = update.to_dict()
    assert d["event"] == "step_started"
    assert d["progress"] == 0.5


def test_status_reporter_clear_history():
    reporter = StatusReporter()
    reporter.report(StatusEvent.TASK_STARTED)
    reporter.clear_history()
    assert len(reporter.history) == 0


def test_multiple_subscribers():
    reporter = StatusReporter()
    updates1 = []
    updates2 = []
    reporter.subscribe(CallbackSubscriber(lambda u: updates1.append(u)))
    reporter.subscribe(CallbackSubscriber(lambda u: updates2.append(u)))

    reporter.report(StatusEvent.COMPLETED)
    assert len(updates1) == 1
    assert len(updates2) == 1
