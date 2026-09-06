"""Tests for Phase 5.12: Final Response Engine."""

from __future__ import annotations

from ultron.goal import Goal, GoalStatus
from ultron.response import GoalResult, ResponseEngine, ResponseOutcome, TaskSummary
from ultron.task import Task, TaskGraph, TaskStatus


class TestResponseEngine:
    def test_all_success(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed({"output": "done"})
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert result.outcome == ResponseOutcome.SUCCESS
        assert result.successful_tasks == 1
        assert result.failed_tasks == 0

    def test_partial_success(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        t2 = Task(id="t2", description="task 2")
        t2.mark_failed("error")
        graph.add_task(t1)
        graph.add_task(t2)

        result = engine.generate(goal, graph)
        assert result.outcome == ResponseOutcome.PARTIAL_SUCCESS

    def test_all_failed(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_failed("error")
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert result.outcome == ResponseOutcome.FAILED

    def test_blocked(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_blocked("dependency failed")
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert result.outcome == ResponseOutcome.BLOCKED

    def test_summary_generation(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert "completed" in result.summary.lower()

    def test_report_generation(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert "Goal Execution Report" in result.detailed_report
        assert "task 1" in result.detailed_report

    def test_task_summaries(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        t1.assigned_agent = "research"
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        assert len(result.task_summaries) == 1
        assert result.task_summaries[0].assigned_agent == "research"

    def test_verification_results(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        graph.add_task(t1)

        result = engine.generate(goal, graph, verification_results={"t1": True})
        assert result.verification_results["t1"]

    def test_limitations(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)

        result = engine.generate(goal, graph, limitations=["timeout on task 2"])
        assert "timeout" in result.limitations[0]

    def test_duration_calculation(self):
        engine = ResponseEngine()
        goal = Goal(
            description="test",
            original_request="do test",
            created_at="2025-01-01T00:00:00+00:00",
        )
        graph = TaskGraph(goal_id=goal.id)

        result = engine.generate(goal, graph)
        assert result.duration_seconds is not None

    def test_result_serialization(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)
        t1 = Task(id="t1", description="task 1")
        t1.mark_completed()
        graph.add_task(t1)

        result = engine.generate(goal, graph)
        d = result.to_dict()
        assert d["outcome"] == "success"
        assert len(d["task_summaries"]) == 1

    def test_empty_graph(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)

        result = engine.generate(goal, graph)
        assert result.planned_tasks == 0

    def test_outputs_collected(self):
        engine = ResponseEngine()
        goal = Goal(description="test", original_request="do test")
        graph = TaskGraph(goal_id=goal.id)

        result = engine.generate(
            goal, graph,
            outputs={"t1": {"description": "task 1", "output": {"data": "val"}}},
        )
        assert "t1" in result.important_outputs
