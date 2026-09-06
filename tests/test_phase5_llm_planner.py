"""Tests for Phase 5.15: LLM Task Planning."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.goal import Goal, GoalComplexity, GoalEngine, GoalPriority, GoalStatus
from ultron.llm.base import ProviderResult
from ultron.llm_planner import LLMGoalPlanner
from ultron.planner_v5 import PlanningError
from ultron.task import TaskGraph, TaskStatus


def _mock_provider(response_text: str) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=response_text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_provider_error() -> MagicMock:
    provider = MagicMock()
    provider.complete.side_effect = Exception("Provider error")
    provider.name = "mock"
    return provider


def _complex_goal() -> Goal:
    return Goal(
        description="Research Python web frameworks and create a comparison report",
        original_request="Research Python web frameworks, compare them, and write a report",
        complexity=GoalComplexity.COMPLEX,
        priority=GoalPriority.NORMAL,
        required_capabilities=["research", "analysis", "writing"],
        required_tools=["read_file", "create_file", "open_url"],
    )


def _moderate_goal() -> Goal:
    return Goal(
        description="Create a file with test content",
        original_request="Create a file called test.txt with hello world",
        complexity=GoalComplexity.MODERATE,
        priority=GoalPriority.NORMAL,
        required_capabilities=["filesystem"],
        required_tools=["create_file"],
    )


class TestLLMPlannerSuccess:
    def test_complex_goal_planned(self):
        """LLM correctly decomposes a complex goal."""
        llm_response = json.dumps({
            "tasks": [
                {
                    "id": "task_1",
                    "description": "Research Python web frameworks",
                    "objective": "Gather information about Python web frameworks",
                    "required_capabilities": ["research"],
                    "required_tools": ["read_file", "open_url"],
                    "dependencies": [],
                    "verification_criteria": ["Research notes collected"],
                    "priority": "normal",
                },
                {
                    "id": "task_2",
                    "description": "Analyze framework pros and cons",
                    "objective": "Compare frameworks based on research",
                    "required_capabilities": ["analysis"],
                    "required_tools": [],
                    "dependencies": ["task_1"],
                    "verification_criteria": ["Analysis complete"],
                    "priority": "normal",
                },
                {
                    "id": "task_3",
                    "description": "Write comparison report",
                    "objective": "Create final comparison document",
                    "required_capabilities": ["writing"],
                    "required_tools": ["create_file"],
                    "dependencies": ["task_2"],
                    "verification_criteria": ["Report file created"],
                    "priority": "normal",
                },
            ],
            "reasoning": "Three-phase approach: research, analysis, then report.",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider, available_tools=["read_file", "create_file", "open_url"])

        goal = _complex_goal()
        graph = planner.plan(goal)

        assert graph.task_count == 3
        assert graph.goal_id == goal.id
        errors = graph.validate()
        assert errors == []

    def test_dependencies_respected(self):
        """Tasks with dependencies are correctly linked."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Step 1", "objective": "First step",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t2", "description": "Step 2", "objective": "Second step",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": ["t1"],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "Sequential tasks.",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider)

        graph = planner.plan(_complex_goal())

        t2 = graph.get_task("t2")
        assert t2 is not None
        assert "t1" in t2.dependencies

    def test_parallel_tasks_detected(self):
        """Independent tasks are correctly identified as parallelizable."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Task A", "objective": "Do A",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t2", "description": "Task B", "objective": "Do B",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t3", "description": "Task C", "objective": "Do C",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": ["t1", "t2"],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "A and B can run in parallel, C depends on both.",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider)

        graph = planner.plan(_complex_goal())

        groups = graph.get_parallel_groups()
        assert len(groups) >= 2
        assert len(groups[0]) == 2


class TestLLMPlannerFallback:
    def test_llm_error_falls_back(self):
        """LLM exception triggers heuristic fallback."""
        provider = _mock_provider_error()
        planner = LLMGoalPlanner(provider)

        goal = _complex_goal()
        graph = planner.plan(goal)

        # Heuristic planner creates tasks for complex goals
        assert graph.task_count > 0

    def test_invalid_json_falls_back(self):
        """Malformed JSON triggers heuristic fallback."""
        provider = _mock_provider("not json at all")
        planner = LLMGoalPlanner(provider)

        graph = planner.plan(_complex_goal())
        assert graph.task_count > 0

    def test_empty_tasks_falls_back(self):
        """LLM returning empty task list triggers fallback."""
        provider = _mock_provider(json.dumps({"tasks": [], "reasoning": "nothing"}))
        planner = LLMGoalPlanner(provider)

        graph = planner.plan(_complex_goal())
        assert graph.task_count > 0

    def test_simple_goal_uses_heuristic(self):
        """Simple goals bypass LLM planning entirely."""
        provider = _mock_provider("{}")
        planner = LLMGoalPlanner(provider)

        goal = Goal(
            description="what is Python?",
            complexity=GoalComplexity.SIMPLE,
        )
        graph = planner.plan(goal)

        assert graph.task_count == 1


class TestLLMPlannerValidation:
    def test_cycle_detection(self):
        """Cyclic dependencies are detected and rejected."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "A", "objective": "A",
                 "required_capabilities": [], "required_tools": [], "dependencies": ["t2"],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t2", "description": "B", "objective": "B",
                 "required_capabilities": [], "required_tools": [], "dependencies": ["t1"],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "cyclic",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider)

        # Cycles cause the LLM plan to be rejected, falling back to heuristic
        graph = planner.plan(_complex_goal())
        assert graph.task_count > 0

    def test_invalid_tool_filtered(self):
        """Tools not in available list are filtered out."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Task", "objective": "Do it",
                 "required_capabilities": ["filesystem"], "required_tools": ["create_file", "rm_rf"],
                 "dependencies": [], "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "test",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider, available_tools=["create_file"])

        graph = planner.plan(_complex_goal())

        t1 = graph.get_task("t1")
        assert "create_file" in t1.required_tools
        assert "rm_rf" not in t1.required_tools

    def test_invalid_capability_filtered(self):
        """Capabilities not in valid set are filtered out."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Task", "objective": "Do it",
                 "required_capabilities": ["research", "hacking"],
                 "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "test",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider)

        graph = planner.plan(_complex_goal())

        t1 = graph.get_task("t1")
        assert "research" in t1.required_capabilities
        assert "hacking" not in t1.required_capabilities

    def test_duplicate_task_ids_handled(self):
        """Duplicate task IDs are handled gracefully."""
        llm_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "A", "objective": "A",
                 "required_capabilities": [], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t1", "description": "B", "objective": "B",
                 "required_capabilities": [], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "duplicate IDs",
        })
        provider = _mock_provider(llm_response)
        planner = LLMGoalPlanner(provider)

        # Should not crash, handles duplicates
        graph = planner.plan(_complex_goal())
        assert graph.task_count >= 1


class TestLLMPlannerBlockedGoal:
    def test_blocked_goal_raises(self):
        """Planning a blocked goal raises PlanningError."""
        provider = _mock_provider("{}")
        planner = LLMGoalPlanner(provider)

        goal = Goal(description="test", status=GoalStatus.BLOCKED)

        try:
            planner.plan(goal)
            assert False, "Should have raised PlanningError"
        except PlanningError:
            pass

    def test_cancelled_goal_raises(self):
        """Planning a cancelled goal raises PlanningError."""
        provider = _mock_provider("{}")
        planner = LLMGoalPlanner(provider)

        goal = Goal(description="test", status=GoalStatus.CANCELLED)

        try:
            planner.plan(goal)
            assert False, "Should have raised PlanningError"
        except PlanningError:
            pass


class TestLLMPlannerReplan:
    def test_replan_after_failure(self):
        """LLM can replan after a task failure."""
        graph = TaskGraph(goal_id="g1")
        from ultron.task import Task
        t1 = Task(id="t1", description="Completed task", status=TaskStatus.COMPLETED)
        t2 = Task(id="t2", description="Failed task", status=TaskStatus.FAILED, error="Tool failed")
        t3 = Task(id="t3", description="Pending task", status=TaskStatus.PENDING, dependencies=["t2"])
        graph.add_task(t1)
        graph.add_task(t2)
        graph.add_task(t3)

        replan_response = json.dumps({
            "tasks": [
                {"id": "t1", "description": "Completed task", "objective": "Done",
                 "required_capabilities": [], "required_tools": [], "dependencies": [],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t2_retry", "description": "Retry failed task", "objective": "Try again",
                 "required_capabilities": ["general"], "required_tools": [], "dependencies": ["t1"],
                 "verification_criteria": [], "priority": "normal"},
                {"id": "t3", "description": "Pending task", "objective": "Continue",
                 "required_capabilities": [], "required_tools": [], "dependencies": ["t2_retry"],
                 "verification_criteria": [], "priority": "normal"},
            ],
            "reasoning": "Replaced failed task with retry.",
        })
        provider = _mock_provider(replan_response)
        planner = LLMGoalPlanner(provider)

        goal = _complex_goal()
        new_graph = planner.replan(goal, graph, "t2")

        assert new_graph is not None
        assert new_graph.task_count == 3

    def test_replan_falls_back_on_error(self):
        """Replan falls back to heuristic on LLM error."""
        graph = TaskGraph(goal_id="g1")
        from ultron.task import Task
        t1 = Task(id="t1", description="Failed", status=TaskStatus.FAILED, error="error")
        graph.add_task(t1)

        provider = _mock_provider_error()
        planner = LLMGoalPlanner(provider)

        goal = _complex_goal()
        new_graph = planner.replan(goal, graph, "t1")

        assert new_graph is not None
