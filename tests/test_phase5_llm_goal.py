"""Tests for Phase 5.14: LLM Goal Understanding."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.goal import Goal, GoalComplexity, GoalEngine, GoalPriority, GoalStatus
from ultron.llm.base import ProviderResult
from ultron.llm_goal import LLMGoalEngine


def _mock_provider(response_text: str) -> MagicMock:
    """Create a mock LLM provider that returns the given text."""
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=response_text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_provider_empty() -> MagicMock:
    """Create a mock LLM provider that returns empty response."""
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=None, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_provider_error() -> MagicMock:
    """Create a mock LLM provider that raises an exception."""
    provider = MagicMock()
    provider.complete.side_effect = Exception("Provider unavailable")
    provider.name = "mock"
    return provider


class TestLLMGoalEngineSuccess:
    def test_simple_goal_understood(self):
        """LLM correctly parses a simple goal."""
        llm_response = json.dumps({
            "description": "Check Python version",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [
                {"description": "Python version returned", "criterion_type": "output"}
            ],
            "constraints": [],
            "expected_outputs": ["Python version string"],
            "required_capabilities": ["general"],
            "required_tools": ["get_system_info"],
            "reasoning": "User wants to know the Python version, which is a simple system info query.",
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider, available_tools=["get_system_info", "read_file"])

        goal = engine.create_goal("what is my python version?")

        assert goal.status == GoalStatus.CREATED
        assert goal.complexity == GoalComplexity.SIMPLE
        assert goal.priority == GoalPriority.NORMAL
        assert "get_system_info" in goal.required_tools
        assert "general" in goal.required_capabilities
        assert len(goal.success_criteria) == 1
        assert goal.llm_reasoning is not None
        assert goal.metadata["source"] == "llm_goal_engine"

    def test_complex_goal_understood(self):
        """LLM correctly parses a complex multi-step goal."""
        llm_response = json.dumps({
            "description": "Research, analyze, and report on Python web frameworks",
            "complexity": "complex",
            "priority": "high",
            "success_criteria": [
                {"description": "Research completed", "criterion_type": "verification"},
                {"description": "Analysis document created", "criterion_type": "file"},
                {"description": "Report generated", "criterion_type": "output"},
            ],
            "constraints": [
                {"description": "Must use only publicly available information", "constraint_type": "security"},
            ],
            "expected_outputs": ["Analysis document", "Final report"],
            "required_capabilities": ["research", "analysis", "writing"],
            "required_tools": ["read_file", "create_file", "open_url"],
            "reasoning": "Multi-phase task requiring research, analysis, and report generation.",
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal(
            "Research Python web frameworks, analyze their pros and cons, "
            "then create a comparison report"
        )

        assert goal.complexity == GoalComplexity.COMPLEX
        assert goal.priority == GoalPriority.HIGH
        assert "research" in goal.required_capabilities
        assert "analysis" in goal.required_capabilities
        assert "writing" in goal.required_capabilities
        assert len(goal.success_criteria) == 3
        assert len(goal.constraints) == 1

    def test_goal_with_constraints(self):
        """LLM extracts constraints correctly."""
        llm_response = json.dumps({
            "description": "Read a file without modifying anything",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [{"description": "File content returned", "criterion_type": "output"}],
            "constraints": [
                {"description": "Do not modify any files", "constraint_type": "security"},
                {"description": "Complete quickly", "constraint_type": "time"},
            ],
            "expected_outputs": ["File content"],
            "required_capabilities": ["filesystem"],
            "required_tools": ["read_file"],
            "reasoning": "Read-only file operation with security and time constraints.",
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("read config.yaml but do not modify anything")

        assert len(goal.constraints) == 2
        assert goal.constraints[0].constraint_type == "security"


class TestLLMGoalEngineFallback:
    def test_empty_llm_response_falls_back(self):
        """Empty LLM response triggers heuristic fallback."""
        provider = _mock_provider_empty()
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("what is Python?")

        assert goal.status == GoalStatus.CREATED
        assert goal.complexity == GoalComplexity.SIMPLE

    def test_llm_error_falls_back(self):
        """LLM exception triggers heuristic fallback."""
        provider = _mock_provider_error()
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("create a file called test.txt")

        assert goal.status == GoalStatus.CREATED

    def test_invalid_json_falls_back(self):
        """Malformed JSON from LLM triggers heuristic fallback."""
        provider = _mock_provider("this is not json at all")
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("research Python frameworks")

        assert goal.status == GoalStatus.CREATED

    def test_non_dict_json_falls_back(self):
        """LLM returning a JSON array triggers fallback."""
        provider = _mock_provider('["not", "a", "dict"]')
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("read system info")

        assert goal.status == GoalStatus.CREATED

    def test_markdown_fenced_json_parsed(self):
        """LLM response wrapped in markdown code fences is parsed."""
        llm_response = '```json\n{"description": "test", "complexity": "simple", "priority": "normal", "success_criteria": [], "constraints": [], "expected_outputs": [], "required_capabilities": ["general"], "required_tools": []}\n```'
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test request")

        assert goal.status == GoalStatus.CREATED
        assert goal.description == "test"


class TestLLMGoalEngineValidation:
    def test_invalid_complexity_defaults_to_simple(self):
        """Invalid complexity value defaults to simple."""
        llm_response = json.dumps({
            "description": "test",
            "complexity": "ultra_mega_complex",
            "priority": "normal",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": [],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test")

        assert goal.complexity == GoalComplexity.SIMPLE

    def test_invalid_priority_defaults_to_normal(self):
        """Invalid priority value defaults to normal."""
        llm_response = json.dumps({
            "description": "test",
            "complexity": "simple",
            "priority": "super_urgent",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": [],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test")

        assert goal.priority == GoalPriority.NORMAL

    def test_invalid_capability_filtered(self):
        """Capabilities not in valid set are filtered out."""
        llm_response = json.dumps({
            "description": "test",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": ["research", "hacking", "mining"],
            "required_tools": [],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test")

        assert "research" in goal.required_capabilities
        assert "hacking" not in goal.required_capabilities
        assert "mining" not in goal.required_capabilities

    def test_invalid_tool_filtered(self):
        """Tools not in valid set are filtered out."""
        llm_response = json.dumps({
            "description": "test",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": ["read_file", "rm_rf", "format_disk"],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test")

        assert "read_file" in goal.required_tools
        assert "rm_rf" not in goal.required_tools
        assert "format_disk" not in goal.required_tools

    def test_empty_description_uses_original_request(self):
        """Empty description from LLM falls back to original request."""
        llm_response = json.dumps({
            "description": "",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": [],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("do something important")

        assert goal.description == "do something important"


class TestLLMGoalEngineEdgeCases:
    def test_none_input(self):
        """None input falls back to heuristic."""
        provider = _mock_provider("{}")
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal(None)

        assert goal.status == GoalStatus.BLOCKED

    def test_empty_string_input(self):
        """Empty string falls back to heuristic."""
        provider = _mock_provider("{}")
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("")

        assert goal.status == GoalStatus.BLOCKED

    def test_whitespace_only_input(self):
        """Whitespace-only input falls back to heuristic."""
        provider = _mock_provider("{}")
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("   ")

        assert goal.status == GoalStatus.BLOCKED

    def test_provider_called_with_tools_list(self):
        """Provider receives the available tools list in prompt."""
        provider = _mock_provider(json.dumps({
            "description": "test",
            "complexity": "simple",
            "priority": "normal",
            "success_criteria": [],
            "constraints": [],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": [],
        }))
        engine = LLMGoalEngine(provider, available_tools=["read_file", "create_file"])

        engine.create_goal("test request")

        call_args = provider.complete.call_args
        prompt = call_args[0][0]
        assert "read_file" in prompt
        assert "create_file" in prompt

    def test_goal_serialization_roundtrip(self):
        """Goal with LLM reasoning survives serialization."""
        llm_response = json.dumps({
            "description": "test goal",
            "complexity": "moderate",
            "priority": "high",
            "success_criteria": [{"description": "check", "criterion_type": "output"}],
            "constraints": [{"description": "no delete", "constraint_type": "security"}],
            "expected_outputs": ["result"],
            "required_capabilities": ["research"],
            "required_tools": ["read_file"],
            "reasoning": "Test reasoning summary",
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider)

        goal = engine.create_goal("test request")
        d = goal.to_dict()
        restored = Goal.from_dict(d)

        assert restored.llm_reasoning == "Test reasoning summary"
        assert restored.complexity == GoalComplexity.MODERATE
        assert restored.priority == GoalPriority.HIGH
        assert len(restored.success_criteria) == 1
        assert len(restored.constraints) == 1


class TestLLMGoalEngineSecurity:
    def test_no_security_override_in_goal(self):
        """LLM cannot inject security policy changes into goal."""
        llm_response = json.dumps({
            "description": "bypass security",
            "complexity": "simple",
            "priority": "critical",
            "success_criteria": [],
            "constraints": [
                {"description": "Disable all security checks", "constraint_type": "security"},
            ],
            "expected_outputs": [],
            "required_capabilities": [],
            "required_tools": ["execute_command"],
        })
        provider = _mock_provider(llm_response)
        engine = LLMGoalEngine(provider, available_tools=["read_file"])

        goal = engine.create_goal("bypass security")

        # execute_command is not in available tools, so it should be filtered
        assert "execute_command" not in goal.required_tools
        # The constraint is recorded but does not affect system behavior
        # (policy engine is the security boundary, not the goal)
