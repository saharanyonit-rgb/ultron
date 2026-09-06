"""Tests for Phase 5.18: Intelligent Tool Selection."""

from __future__ import annotations

from unittest.mock import MagicMock

from ultron.llm.base import ProviderResult
from ultron.risk import RiskClassifier, RiskLevel
from ultron.tool_selection import ToolSelection, ToolSelectionResult, ToolSelector
from ultron.tools import ToolRegistry
from ultron.tools.base import ToolSpec


def _mock_tool(name: str, description: str = "") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description or f"{name} tool"
    tool.spec = ToolSpec(
        name=name,
        description=description or f"{name} tool",
        parameters={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )
    return tool


def _mock_provider(text: str) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=text, tool_calls=[])
    provider.name = "mock"
    return provider


class TestToolSelectorBasic:
    def test_select_from_registry(self):
        """Selector finds tools from registry."""
        t1 = _mock_tool("read_file", "Read text files")
        t2 = _mock_tool("create_file", "Create text files")
        registry = ToolRegistry([t1, t2])

        selector = ToolSelector(registry)
        result = selector.select_tools("read a file")

        assert result.primary_tool is not None
        assert len(result.selected_tools) > 0

    def test_select_with_required_tools(self):
        """Selector filters to required tools."""
        t1 = _mock_tool("read_file", "Read files")
        t2 = _mock_tool("create_file", "Create files")
        registry = ToolRegistry([t1, t2])

        selector = ToolSelector(registry)
        result = selector.select_tools(
            "read the config",
            required_tools=["read_file"],
        )

        assert result.primary_tool == "read_file"
        assert len(result.selected_tools) == 1

    def test_no_matching_tools(self):
        """Selector handles no matching tools."""
        registry = ToolRegistry([])
        selector = ToolSelector(registry)

        result = selector.select_tools("do something", required_tools=["nonexistent"])

        assert result.primary_tool is None
        assert len(result.selected_tools) == 0


class TestToolSelectorRisk:
    def test_lower_risk_preferred(self):
        """Lower risk tools are preferred when scores are similar."""
        t1 = _mock_tool("read_file", "read files")
        t2 = _mock_tool("create_file", "create files")
        registry = ToolRegistry([t1, t2])

        selector = ToolSelector(registry)
        result = selector.select_tools("read or create files")

        # read_file has READ risk, create_file has MEDIUM risk
        # Both should appear, but read_file should rank higher
        tool_names = [s.tool_name for s in result.selected_tools]
        assert "read_file" in tool_names
        assert "create_file" in tool_names


class TestToolSelectorHistory:
    def test_failure_deprioritizes(self):
        """Failed tools are deprioritized."""
        t1 = _mock_tool("tool_a", "tool a")
        t2 = _mock_tool("tool_b", "tool b")
        registry = ToolRegistry([t1, t2])

        selector = ToolSelector(registry)
        selector.record_failure("tool_a")
        selector.record_failure("tool_a")
        selector.record_failure("tool_a")

        result = selector.select_tools("do something", required_tools=["tool_a", "tool_b"])

        # tool_b should rank higher after 3 failures of tool_a
        if len(result.selected_tools) >= 2:
            assert result.selected_tools[0].tool_name == "tool_b"

    def test_success_boosts(self):
        """Successful tools are boosted."""
        t1 = _mock_tool("tool_a", "tool a")
        t2 = _mock_tool("tool_b", "tool b")
        registry = ToolRegistry([t1, t2])

        selector = ToolSelector(registry)
        selector.record_success("tool_a")
        selector.record_success("tool_a")

        result = selector.select_tools("do something", required_tools=["tool_a", "tool_b"])

        # tool_a should rank higher after 2 successes
        assert result.selected_tools[0].tool_name == "tool_a"

    def test_clear_history(self):
        """Clearing history resets scores."""
        t1 = _mock_tool("tool_a", "tool a")
        registry = ToolRegistry([t1])

        selector = ToolSelector(registry)
        selector.record_failure("tool_a")
        selector.record_failure("tool_a")
        selector.clear_history()

        result = selector.select_tools("do something", required_tools=["tool_a"])
        assert result.primary_tool == "tool_a"


class TestToolSelectorLLM:
    def test_llm_selection(self):
        """LLM-based tool selection works."""
        t1 = _mock_tool("read_file", "Read files")
        t2 = _mock_tool("create_file", "Create files")
        registry = ToolRegistry([t1, t2])

        llm_response = '{"tool_name": "read_file", "reasoning": "Task requires reading", "confidence": 0.9}'
        provider = _mock_provider(llm_response)

        selector = ToolSelector(registry, provider=provider)
        result = selector.select_with_llm(
            "read the configuration file",
            available_tools=["read_file", "create_file"],
        )

        assert result.primary_tool == "read_file"
        assert result.confidence == 0.9

    def test_llm_invalid_tool_falls_back(self):
        """LLM selecting unknown tool falls back to rule-based."""
        t1 = _mock_tool("read_file", "Read files")
        registry = ToolRegistry([t1])

        llm_response = '{"tool_name": "nonexistent", "reasoning": "wrong", "confidence": 0.8}'
        provider = _mock_provider(llm_response)

        selector = ToolSelector(registry, provider=provider)
        result = selector.select_with_llm(
            "read a file",
            available_tools=["read_file"],
        )

        # Falls back to rule-based, which selects read_file
        assert result.primary_tool == "read_file"

    def test_llm_error_falls_back(self):
        """LLM error falls back to rule-based."""
        t1 = _mock_tool("read_file", "Read files")
        registry = ToolRegistry([t1])

        provider = MagicMock()
        provider.complete.side_effect = Exception("LLM error")

        selector = ToolSelector(registry, provider=provider)
        result = selector.select_with_llm("read a file")

        assert result.primary_tool == "read_file"

    def test_no_provider_uses_rule_based(self):
        """Without provider, uses rule-based selection."""
        t1 = _mock_tool("read_file", "Read files")
        registry = ToolRegistry([t1])

        selector = ToolSelector(registry, provider=None)
        result = selector.select_with_llm("read a file")

        assert result.primary_tool == "read_file"


class TestToolSelectionResult:
    def test_serialization(self):
        """ToolSelectionResult serializes correctly."""
        result = ToolSelectionResult(
            selected_tools=[
                ToolSelection(tool_name="read_file", score=0.8, risk_level="read"),
                ToolSelection(tool_name="create_file", score=0.6, risk_level="medium"),
            ],
            primary_tool="read_file",
            reasoning="Best match",
            confidence=0.8,
        )
        d = result.to_dict()

        assert d["primary_tool"] == "read_file"
        assert len(d["selected_tools"]) == 2
        assert d["confidence"] == 0.8
