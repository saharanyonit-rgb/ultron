"""Tests for LLM planner retry and full-goal-planning changes."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, call

from ultron.goal import Goal, GoalComplexity, GoalStatus
from ultron.llm.base import ProviderResult
from ultron.llm_planner import LLMGoalPlanner
from ultron.planner_v5 import GoalPlanner, PlanningError
from ultron.task import TaskGraph


def _mock_provider(text: str) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_provider_sequence(texts: list[str]) -> MagicMock:
    """Provider that returns different responses on each call."""
    provider = MagicMock()
    provider.complete.side_effect = [
        ProviderResult(text=t, tool_calls=[]) for t in texts
    ]
    provider.name = "mock"
    return provider


def _valid_plan_json(task_count: int = 2) -> str:
    """Generate valid planning JSON."""
    tasks = []
    for i in range(1, task_count + 1):
        tasks.append({
            "id": f"task_{i}",
            "description": f"Task {i}",
            "objective": f"Do task {i}",
            "required_capabilities": ["general"],
            "required_tools": [],
            "dependencies": [f"task_{i-1}"] if i > 1 else [],
            "verification_criteria": [f"Task {i} completed"],
            "priority": "normal",
        })
    return json.dumps({"tasks": tasks, "reasoning": "test plan"})


def _simple_goal() -> Goal:
    return Goal(
        id="g1",
        description="List files in current directory",
        original_request="list files",
        complexity=GoalComplexity.SIMPLE,
        status=GoalStatus.CREATED,
    )


def _complex_goal() -> Goal:
    return Goal(
        id="g2",
        description="Research Python web frameworks, compare them, and write a summary report",
        original_request="research, compare, and report",
        complexity=GoalComplexity.COMPLEX,
        status=GoalStatus.CREATED,
    )


# ═══════════════════════════════════════════════════════════════════
# Remove SIMPLE Bypass
# ═══════════════════════════════════════════════════════════════════

class TestNoSimpleBypass:
    def test_simple_goal_uses_llm(self):
        """Simple goals now go through LLM, not heuristic."""
        provider = _mock_provider(_valid_plan_json(1))
        planner = LLMGoalPlanner(provider=provider)
        goal = _simple_goal()

        graph = planner.plan(goal)

        # LLM should have been called
        provider.complete.assert_called()
        assert graph is not None
        assert graph.task_count >= 1

    def test_simple_goal_falls_back_on_llm_failure(self):
        """Simple goals still fall back to heuristic on LLM failure."""
        provider = MagicMock()
        provider.complete.side_effect = Exception("LLM error")
        planner = LLMGoalPlanner(provider=provider)
        goal = _simple_goal()

        graph = planner.plan(goal)

        # Should fall back to heuristic
        assert graph is not None
        assert graph.task_count >= 1

    def test_complex_goal_still_uses_llm(self):
        """Complex goals still use LLM planning."""
        provider = _mock_provider(_valid_plan_json(4))
        planner = LLMGoalPlanner(provider=provider)
        goal = _complex_goal()

        graph = planner.plan(goal)
        provider.complete.assert_called()
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════
# Retry with Error Feedback
# ═══════════════════════════════════════════════════════════════════

class TestRetryLogic:
    def test_retry_on_invalid_json(self):
        """Retries when LLM returns invalid JSON."""
        invalid_json = "this is not json"
        valid_json = _valid_plan_json(2)

        provider = _mock_provider_sequence([invalid_json, valid_json])
        planner = LLMGoalPlanner(provider=provider)
        goal = _complex_goal()

        graph = planner.plan(goal)

        # Should have retried and succeeded
        assert provider.complete.call_count >= 2
        assert graph is not None
        assert graph.task_count == 2

    def test_retry_on_validation_failure(self):
        """Retries when plan fails validation (e.g., missing required fields)."""
        # Plan with empty tasks list (fails validation)
        invalid_plan = json.dumps({"tasks": [], "reasoning": "no tasks"})
        valid_plan = _valid_plan_json(2)

        provider = _mock_provider_sequence([invalid_plan, valid_plan])
        planner = LLMGoalPlanner(provider=provider)
        goal = _complex_goal()

        graph = planner.plan(goal)

        assert provider.complete.call_count >= 2
        assert graph is not None

    def test_fallback_after_max_retries(self):
        """Falls back to heuristic after max retries exhausted."""
        invalid_json = "not json at all"

        # All attempts return invalid JSON
        provider = _mock_provider_sequence([invalid_json, invalid_json, invalid_json])
        planner = LLMGoalPlanner(provider=provider)
        goal = _complex_goal()

        graph = planner.plan(goal)

        # Should fall back to heuristic
        assert graph is not None
        assert graph.task_count >= 1

    def test_success_on_first_attempt_no_retry(self):
        """No retry needed when first attempt succeeds."""
        valid_json = _valid_plan_json(2)
        provider = _mock_provider(valid_json)
        planner = LLMGoalPlanner(provider=provider)
        goal = _complex_goal()

        graph = planner.plan(goal)

        # Only one call to complete
        assert provider.complete.call_count == 1
        assert graph is not None


# ═══════════════════════════════════════════════════════════════════
# Blocked Goal Handling
# ═══════════════════════════════════════════════════════════════════

class TestBlockedGoals:
    def test_blocked_goal_raises(self):
        """Planning a blocked goal raises PlanningError."""
        provider = _mock_provider("{}")
        planner = LLMGoalPlanner(provider=provider)
        goal = Goal(
            id="g1",
            description="test",
            status=GoalStatus.BLOCKED,
        )

        try:
            planner.plan(goal)
            assert False, "Should have raised PlanningError"
        except PlanningError:
            pass

    def test_cancelled_goal_raises(self):
        """Planning a cancelled goal raises PlanningError."""
        provider = _mock_provider("{}")
        planner = LLMGoalPlanner(provider=provider)
        goal = Goal(
            id="g1",
            description="test",
            status=GoalStatus.CANCELLED,
        )

        try:
            planner.plan(goal)
            assert False, "Should have raised PlanningError"
        except PlanningError:
            pass
