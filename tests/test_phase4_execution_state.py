"""Tests for execution state persistence (Phase 4)."""

from __future__ import annotations

from ultron.execution_state import (
    ExecutionStateStore,
    StepState,
    TaskState,
    TaskStatus,
)


def test_step_state_creation():
    step = StepState(step_id="s1", objective="test step")
    assert step.step_id == "s1"
    assert step.status == "pending"
    assert step.retry_count == 0


def test_step_state_to_dict():
    step = StepState(step_id="s1", objective="test", status="running")
    d = step.to_dict()
    assert d["step_id"] == "s1"
    assert d["status"] == "running"


def test_step_state_from_dict():
    step = StepState.from_dict({"step_id": "s1", "objective": "test", "status": "succeeded"})
    assert step.step_id == "s1"
    assert step.status == "succeeded"


def test_task_state_creation():
    task = TaskState(task_id="t1", description="test task")
    assert task.task_id == "t1"
    assert task.status == TaskStatus.PENDING


def test_task_state_to_dict():
    task = TaskState(task_id="t1", description="test")
    d = task.to_dict()
    assert d["task_id"] == "t1"
    assert d["status"] == "pending"


def test_task_state_from_dict():
    task = TaskState.from_dict({
        "task_id": "t1",
        "description": "test",
        "status": "running",
        "steps": [{"step_id": "s1", "status": "completed"}],
    })
    assert task.task_id == "t1"
    assert task.status == TaskStatus.RUNNING
    assert len(task.steps) == 1


def test_task_state_completed_steps():
    task = TaskState(task_id="t1")
    task.steps = [
        StepState(step_id="s1", status="succeeded"),
        StepState(step_id="s2", status="failed"),
        StepState(step_id="s3", status="pending"),
    ]
    assert len(task.completed_steps) == 1
    assert len(task.failed_steps) == 1
    assert len(task.pending_steps) == 1


def test_task_state_progress():
    task = TaskState(task_id="t1")
    task.steps = [
        StepState(step_id="s1", status="succeeded"),
        StepState(step_id="s2", status="succeeded"),
        StepState(step_id="s3", status="pending"),
    ]
    assert task.progress == 2 / 3


def test_execution_state_store_save_load(tmp_path):
    store = ExecutionStateStore(tmp_path / "state.json")
    task = TaskState(task_id="t1", description="test")
    store.save_task(task)

    loaded = store.load_task("t1")
    assert loaded is not None
    assert loaded.task_id == "t1"


def test_execution_state_store_list_tasks(tmp_path):
    store = ExecutionStateStore(tmp_path / "state.json")
    store.save_task(TaskState(task_id="t1", status=TaskStatus.RUNNING))
    store.save_task(TaskState(task_id="t2", status=TaskStatus.COMPLETED))

    running = store.list_tasks(TaskStatus.RUNNING)
    assert len(running) == 1
    assert running[0].task_id == "t1"


def test_execution_state_store_delete_task(tmp_path):
    store = ExecutionStateStore(tmp_path / "state.json")
    store.save_task(TaskState(task_id="t1"))
    assert store.delete_task("t1") is True
    assert store.load_task("t1") is None


def test_execution_state_store_update_step(tmp_path):
    store = ExecutionStateStore(tmp_path / "state.json")
    task = TaskState(task_id="t1")
    task.steps = [StepState(step_id="s1")]
    store.save_task(task)

    store.update_step("t1", "s1", "running")
    loaded = store.load_task("t1")
    assert loaded.steps[0].status == "running"
    assert loaded.steps[0].started_at is not None


def test_execution_state_store_get_incomplete(tmp_path):
    store = ExecutionStateStore(tmp_path / "state.json")
    store.save_task(TaskState(task_id="t1", status=TaskStatus.RUNNING))
    store.save_task(TaskState(task_id="t2", status=TaskStatus.COMPLETED))
    store.save_task(TaskState(task_id="t3", status=TaskStatus.PAUSED))

    incomplete = store.get_incomplete_tasks()
    assert len(incomplete) == 2


def test_execution_state_store_persistence(tmp_path):
    path = tmp_path / "state.json"
    store1 = ExecutionStateStore(path)
    store1.save_task(TaskState(task_id="t1"))

    store2 = ExecutionStateStore(path)
    loaded = store2.load_task("t1")
    assert loaded is not None
    assert loaded.task_id == "t1"
