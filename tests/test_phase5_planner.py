"""Tests for Phase 5.3: Goal Planner."""

from __future__ import annotations

from ultron.goal import Goal, GoalComplexity, GoalEngine
from ultron.planner_v5 import GoalPlanner, PlanningError
from ultron.task import TaskGraph, TaskStatus


class TestGoalPlanner:
    def test_simple_plan(self):
        planner = GoalPlanner()
        goal = Goal(
            description="read a file",
            original_request="read a file",
            complexity=GoalComplexity.SIMPLE,
            required_tools=["read_file"],
        )
        graph = planner.plan(goal)
        assert graph.task_count == 1
        assert not graph.has_cycle()
        errors = graph.validate()
        assert len(errors) == 0

    def test_moderate_plan(self):
        planner = GoalPlanner()
        goal = Goal(
            description="analyze the data and create a report",
            original_request="analyze the data and create a report",
            complexity=GoalComplexity.MODERATE,
            required_capabilities=["analysis"],
            required_tools=["create_file"],
        )
        graph = planner.plan(goal)
        assert graph.task_count >= 2
        errors = graph.validate()
        assert len(errors) == 0

    def test_complex_plan(self):
        planner = GoalPlanner()
        goal = Goal(
            description="research topic, analyze findings, create report, and verify",
            original_request="research topic, analyze findings, create report, and verify",
            complexity=GoalComplexity.COMPLEX,
            required_capabilities=["research", "analysis", "writing"],
            required_tools=["read_file", "search_files", "create_file"],
        )
        graph = planner.plan(goal)
        assert graph.task_count >= 3
        assert not graph.has_cycle()
        errors = graph.validate()
        assert len(errors) == 0

    def test_plan_blocked_goal(self):
        planner = GoalPlanner()
        goal = Goal(
            description="blocked goal",
            status="blocked",
        )
        try:
            planner.plan(goal)
            assert False, "Should have raised PlanningError"
        except PlanningError:
            pass

    def test_plan_has_dependencies(self):
        planner = GoalPlanner()
        goal = Goal(
            description="first analyze, then create report",
            original_request="first analyze, then create report",
            complexity=GoalComplexity.MODERATE,
            required_capabilities=["analysis", "writing"],
            required_tools=["create_file"],
        )
        graph = planner.plan(goal)
        tasks_with_deps = [t for t in graph.tasks if t.dependencies]
        assert len(tasks_with_deps) > 0

    def test_simple_plan_no_unnecessary_decomposition(self):
        planner = GoalPlanner()
        goal = Goal(
            description="open notepad",
            original_request="open notepad",
            complexity=GoalComplexity.SIMPLE,
            required_tools=["open_app"],
        )
        graph = planner.plan(goal)
        assert graph.task_count == 1

    def test_replan(self):
        planner = GoalPlanner()
        goal = Goal(
            description="multi-step task",
            original_request="multi-step task",
            complexity=GoalComplexity.MODERATE,
            required_capabilities=["analysis", "writing"],
            required_tools=["create_file"],
        )
        graph = planner.plan(goal)
        first_task = graph.tasks[0]
        first_task.mark_running()
        first_task.mark_failed("error")
        graph.on_task_failed(first_task.id, "error")

        new_graph = planner.replan(goal, graph, first_task.id)
        assert new_graph.task_count >= 1
        errors = new_graph.validate()
        assert len(errors) == 0

    def test_plan_via_goal_engine(self):
        engine = GoalEngine()
        planner = GoalPlanner()

        goal = engine.create_goal(
            "Research Python web frameworks and create a comparison report"
        )
        graph = planner.plan(goal)
        assert graph.task_count >= 1
        assert not graph.has_cycle()

    def test_plan_preserves_goal_id(self):
        planner = GoalPlanner()
        goal = Goal(
            id="test-goal-123",
            description="test",
            original_request="test",
            complexity=GoalComplexity.SIMPLE,
        )
        graph = planner.plan(goal)
        assert graph.goal_id == "test-goal-123"
