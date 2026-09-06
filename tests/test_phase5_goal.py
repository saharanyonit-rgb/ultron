"""Tests for Phase 5.1: Goal Engine and Goal Model."""

from __future__ import annotations

from ultron.goal import (
    Goal,
    GoalComplexity,
    GoalConstraint,
    GoalEngine,
    GoalPriority,
    GoalStatus,
    SuccessCriteria,
)


class TestGoalModel:
    def test_goal_creation_defaults(self):
        goal = Goal(description="test goal")
        assert goal.description == "test goal"
        assert goal.status == GoalStatus.CREATED
        assert goal.complexity == GoalComplexity.SIMPLE
        assert goal.priority == GoalPriority.NORMAL
        assert len(goal.id) == 12

    def test_goal_serialization(self):
        goal = Goal(
            description="test",
            original_request="do something",
            status=GoalStatus.EXECUTING,
            complexity=GoalComplexity.COMPLEX,
            priority=GoalPriority.HIGH,
            success_criteria=[SuccessCriteria(description="check 1")],
            constraints=[GoalConstraint(description="constraint 1")],
        )
        d = goal.to_dict()
        restored = Goal.from_dict(d)
        assert restored.description == "test"
        assert restored.status == GoalStatus.EXECUTING
        assert restored.complexity == GoalComplexity.COMPLEX
        assert len(restored.success_criteria) == 1
        assert len(restored.constraints) == 1

    def test_goal_needs_planning(self):
        simple = Goal(complexity=GoalComplexity.SIMPLE)
        assert not simple.needs_planning
        moderate = Goal(complexity=GoalComplexity.MODERATE)
        assert moderate.needs_planning
        complex = Goal(complexity=GoalComplexity.COMPLEX)
        assert complex.needs_planning

    def test_goal_status_transitions(self):
        goal = Goal(description="test")
        goal.update_status(GoalStatus.PLANNING)
        assert goal.status == GoalStatus.PLANNING
        assert goal.completed_at is None
        goal.update_status(GoalStatus.COMPLETED)
        assert goal.status == GoalStatus.COMPLETED
        assert goal.completed_at is not None

    def test_success_criteria_serialization(self):
        c = SuccessCriteria(description="check", criterion_type="file", expected_value="path.txt")
        d = c.to_dict()
        restored = SuccessCriteria.from_dict(d)
        assert restored.description == "check"
        assert restored.criterion_type == "file"

    def test_constraint_serialization(self):
        c = GoalConstraint(description="no delete", constraint_type="security")
        d = c.to_dict()
        restored = GoalConstraint.from_dict(d)
        assert restored.description == "no delete"


class TestGoalEngine:
    def test_simple_goal(self):
        engine = GoalEngine()
        goal = engine.create_goal("what is Python?")
        assert goal.complexity == GoalComplexity.SIMPLE
        assert goal.status == GoalStatus.CREATED
        assert goal.original_request == "what is Python?"

    def test_complex_goal(self):
        engine = GoalEngine()
        goal = engine.create_goal(
            "Research Python frameworks, analyze their pros and cons, "
            "then create a comparison report, and verify the report is accurate"
        )
        assert goal.complexity in (GoalComplexity.MODERATE, GoalComplexity.COMPLEX)
        assert "research" in goal.required_capabilities

    def test_moderate_goal(self):
        engine = GoalEngine()
        goal = engine.create_goal("create a file called test.txt with content")
        assert goal.complexity in (GoalComplexity.MODERATE, GoalComplexity.COMPLEX)

    def test_empty_input(self):
        engine = GoalEngine()
        goal = engine.create_goal("")
        assert goal.status == GoalStatus.BLOCKED

    def test_whitespace_input(self):
        engine = GoalEngine()
        goal = engine.create_goal("   ")
        assert goal.status == GoalStatus.BLOCKED

    def test_none_input(self):
        engine = GoalEngine()
        goal = engine.create_goal(None)
        assert goal.status == GoalStatus.BLOCKED

    def test_constraints_detected(self):
        engine = GoalEngine()
        goal = engine.create_goal("do not delete any files")
        assert len(goal.constraints) > 0

    def test_priority_detection(self):
        engine = GoalEngine()
        urgent = engine.create_goal("urgent: fix this now")
        assert urgent.priority in (GoalPriority.CRITICAL, GoalPriority.HIGH)
        low = engine.create_goal("low priority: when you can, no rush")
        assert low.priority == GoalPriority.LOW

    def test_capabilities_detected(self):
        engine = GoalEngine()
        goal = engine.create_goal("research the best Python libraries")
        assert "research" in goal.required_capabilities

    def test_tools_detected(self):
        engine = GoalEngine()
        goal = engine.create_goal("write a file with content")
        assert "create_file" in goal.required_tools

    def test_success_criteria_extracted(self):
        engine = GoalEngine()
        goal = engine.create_goal("verify the file exists")
        assert len(goal.success_criteria) > 0

    def test_metadata_populated(self):
        engine = GoalEngine()
        goal = engine.create_goal("test request with multiple words here")
        assert "input_length" in goal.metadata
        assert "word_count" in goal.metadata
