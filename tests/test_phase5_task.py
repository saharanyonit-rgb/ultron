"""Tests for Phase 5.2: Task Model and Task Graph."""

from __future__ import annotations

import json

from ultron.task import Task, TaskGraph, TaskPriority, TaskStatus


class TestTaskModel:
    def test_task_creation(self):
        task = Task(description="do something", objective="achieve goal")
        assert task.description == "do something"
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0

    def test_task_lifecycle(self):
        task = Task(description="test")
        assert task.status == TaskStatus.PENDING
        task.mark_running()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        task.mark_completed({"result": "done"})
        assert task.status == TaskStatus.COMPLETED
        assert task.output_data == {"result": "done"}
        assert task.completed_at is not None

    def test_task_failure(self):
        task = Task(description="test")
        task.mark_running()
        task.mark_failed("something broke")
        assert task.status == TaskStatus.FAILED
        assert task.error == "something broke"

    def test_task_blocked(self):
        task = Task(description="test")
        task.mark_blocked("dependency failed")
        assert task.status == TaskStatus.BLOCKED

    def test_task_cancelled(self):
        task = Task(description="test")
        task.mark_cancelled()
        assert task.status == TaskStatus.CANCELLED

    def test_task_can_retry(self):
        task = Task(description="test", max_retries=3)
        task.mark_failed("error")
        assert task.can_retry
        task.retry_count = 3
        assert not task.can_retry

    def test_task_is_terminal(self):
        task = Task(description="test")
        assert not task.is_terminal
        task.mark_completed()
        assert task.is_terminal
        task2 = Task(description="test2")
        task2.mark_failed("err")
        assert task2.is_terminal
        task3 = Task(description="test3")
        task3.mark_cancelled()
        assert task3.is_terminal

    def test_task_duration(self):
        task = Task(description="test")
        task.started_at = "2025-01-01T00:00:00+00:00"
        task.completed_at = "2025-01-01T00:00:10+00:00"
        assert task.duration_seconds == 10.0

    def test_task_serialization(self):
        task = Task(
            description="test",
            objective="goal",
            dependencies=["dep1"],
            required_tools=["read_file"],
            priority=TaskPriority.HIGH,
        )
        d = task.to_dict()
        restored = Task.from_dict(d)
        assert restored.description == "test"
        assert restored.dependencies == ["dep1"]
        assert restored.required_tools == ["read_file"]
        assert restored.priority == TaskPriority.HIGH


class TestTaskGraph:
    def test_empty_graph(self):
        graph = TaskGraph()
        assert graph.task_count == 0
        assert graph.is_complete
        assert graph.progress == 0.0

    def test_add_task(self):
        graph = TaskGraph()
        task = Task(description="t1")
        graph.add_task(task)
        assert graph.task_count == 1
        assert graph.get_task(task.id) is task

    def test_duplicate_task_raises(self):
        graph = TaskGraph()
        task = Task(id="t1", description="test")
        graph.add_task(task)
        try:
            graph.add_task(Task(id="t1", description="test2"))
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_add_dependency(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="first")
        t2 = Task(id="t2", description="second")
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_dependency("t2", "t1")
        assert "t1" in t2.dependencies
        assert "t2" in t1.dependents

    def test_self_dependency_raises(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="test")
        graph.add_task(t1)
        try:
            graph.add_dependency("t1", "t1")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_cycle_detection(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a", dependencies=["t2"])
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        assert graph.has_cycle()

    def test_no_cycle(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        t3 = Task(id="t3", description="c", dependencies=["t1", "t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)
        assert not graph.has_cycle()

    def test_ready_tasks(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        ready = graph.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t1"

    def test_ready_after_completion(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.on_task_completed("t1")
        ready = graph.ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "t2"

    def test_blocked_on_failure(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        blocked = graph.on_task_failed("t1", "error")
        assert "t2" in blocked
        assert t2.status == TaskStatus.BLOCKED

    def test_progress(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b")
        graph.add_task(t1)
        graph.add_task(t2)
        assert graph.progress == 0.0
        graph.on_task_completed("t1")
        assert graph.progress == 0.5
        graph.on_task_completed("t2")
        assert graph.progress == 1.0

    def test_parallel_groups(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b")
        t3 = Task(id="t3", description="c", dependencies=["t1", "t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)
        groups = graph.get_parallel_groups()
        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 1

    def test_serialization(self):
        graph = TaskGraph(goal_id="g1", description="test")
        graph.add_task(Task(id="t1", description="a"))
        graph.add_task(Task(id="t2", description="b", dependencies=["t1"]))
        serialized = graph.serialize()
        restored = TaskGraph.deserialize(serialized)
        assert restored.goal_id == "g1"
        assert restored.task_count == 2

    def test_remove_task(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a")
        t2 = Task(id="t2", description="b", dependencies=["t1"])
        graph.add_task(t1)
        graph.add_task(t2)
        assert graph.remove_task("t1")
        assert graph.task_count == 1
        assert "t1" not in t2.dependencies

    def test_validation(self):
        graph = TaskGraph()
        t1 = Task(id="t1", description="a", dependencies=["unknown"])
        graph.add_task(t1)
        errors = graph.validate()
        assert len(errors) > 0

    def test_summary(self):
        graph = TaskGraph(goal_id="g1")
        graph.add_task(Task(id="t1", description="a"))
        summary = graph.summary()
        assert summary["goal_id"] == "g1"
        assert summary["total_tasks"] == 1
