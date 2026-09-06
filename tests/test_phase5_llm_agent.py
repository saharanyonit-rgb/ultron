"""Tests for Phase 5.16: Real LLM Agents."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.agents import AgentCapability, AgentSpec
from ultron.agents.llm_agent import (
    AgentDecision,
    AgentDecisionType,
    AgentTrace,
    LLMAgent,
)
from ultron.llm.base import ProviderResult, ToolCall, ToolResult
from ultron.tools import Tool, ToolSpec


def _mock_provider(responses):
    """Create a mock provider that returns a sequence of responses."""
    provider = MagicMock()
    if isinstance(responses, list):
        provider.complete.side_effect = [
            ProviderResult(text=r if isinstance(r, str) else r[0],
                          tool_calls=r[1] if isinstance(r, tuple) else [])
            for r in responses
        ]
    else:
        provider.complete.return_value = ProviderResult(text=responses, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_tool(name: str = "test_tool") -> MagicMock:
    """Create a mock tool."""
    tool = MagicMock()
    tool.name = name
    tool.spec = ToolSpec(
        name=name,
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )
    tool.run.return_value = {"result": "tool output"}
    return tool


class TestLLMAgentDirectAnswer:
    def test_direct_text_answer(self):
        """Agent returns direct text when LLM provides no tool calls."""
        provider = _mock_provider("The answer is 42")
        tool = _mock_tool()
        agent = LLMAgent(provider, [tool])

        result = agent.run("what is the answer?")

        assert "42" in result

    def test_direct_answer_trace(self):
        """Trace shows completion with no tool calls."""
        provider = _mock_provider("Done")
        agent = LLMAgent(provider, [])

        trace = agent.run_with_trace("simple question")

        assert trace.completed
        assert trace.tool_calls_made == 0
        assert trace.iterations == 1
        assert trace.final_answer == "Done"


class TestLLMAgentToolExecution:
    def test_single_tool_call(self):
        """Agent makes a tool call and returns the result."""
        tool = _mock_tool("read_file")
        tool.run.return_value = {"content": "file contents"}

        # First call: LLM requests tool. Second call: LLM completes.
        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="read_file", arguments={"path": "test.txt"})]),
            "The file contains: file contents",
        ])
        agent = LLMAgent(provider, [tool])

        trace = agent.run_with_trace("read test.txt")

        assert trace.tool_calls_made == 1
        assert trace.completed
        tool.run.assert_called_once_with(path="test.txt")

    def test_multiple_tool_calls(self):
        """Agent makes multiple sequential tool calls."""
        tool1 = _mock_tool("read_file")
        tool1.run.return_value = {"content": "data"}
        tool2 = _mock_tool("create_file")
        tool2.run.return_value = {"created": True}

        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="read_file", arguments={"path": "in.txt"})]),
            (None, [ToolCall(id="c2", name="create_file", arguments={"path": "out.txt", "content": "data"})]),
            "Files processed successfully",
        ])
        agent = LLMAgent(provider, [tool1, tool2])

        trace = agent.run_with_trace("read input and create output")

        assert trace.tool_calls_made == 2
        assert trace.completed

    def test_unknown_tool_handled(self):
        """Agent handles calls to unknown tools gracefully."""
        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="nonexistent_tool", arguments={})]),
            "Tool was not available",
        ])
        agent = LLMAgent(provider, [])

        trace = agent.run_with_trace("do something")

        assert trace.tool_calls_made == 1
        assert trace.completed

    def test_tool_exception_handled(self):
        """Agent handles tool execution exceptions gracefully."""
        tool = _mock_tool("failing_tool")
        tool.run.side_effect = RuntimeError("Tool broke")

        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="failing_tool", arguments={})]),
            "The tool failed, but I can still answer",
        ])
        agent = LLMAgent(provider, [tool])

        trace = agent.run_with_trace("try the tool")

        assert trace.tool_calls_made == 1
        assert trace.completed


class TestLLMAgentIterationLimit:
    def test_iteration_limit_reached(self):
        """Agent stops when iteration limit is reached."""
        tool = _mock_tool("loop_tool")

        # Always request more tool calls
        provider = MagicMock()
        provider.complete.return_value = ProviderResult(
            text=None,
            tool_calls=[ToolCall(id="c1", name="loop_tool", arguments={})],
        )
        provider.name = "mock"

        agent = LLMAgent(provider, [tool], max_iterations=3)
        trace = agent.run_with_trace("loop forever")

        assert trace.iterations == 3
        assert trace.error is not None
        assert "limit" in trace.error.lower()


class TestLLMAgentCapabilities:
    def test_agent_spec_defaults(self):
        """LLMAgent has sensible defaults."""
        provider = _mock_provider("ok")
        agent = LLMAgent(provider, [])

        assert agent.spec.name == "llm_agent"
        assert AgentCapability.GENERAL in agent.spec.capabilities

    def test_custom_spec(self):
        """LLMAgent accepts custom AgentSpec."""
        provider = _mock_provider("ok")
        spec = AgentSpec(
            name="custom",
            description="Custom agent",
            capabilities=[AgentCapability.RESEARCH],
            allowed_tools=["read_file"],
        )
        agent = LLMAgent(provider, [], spec=spec)

        assert agent.spec.name == "custom"
        assert AgentCapability.RESEARCH in agent.spec.capabilities

    def test_tool_filtering_by_spec(self):
        """Agent only uses tools allowed by spec."""
        tool1 = _mock_tool("read_file")
        tool2 = _mock_tool("create_file")
        spec = AgentSpec(
            name="reader",
            description="Read only",
            capabilities=[AgentCapability.GENERAL],
            allowed_tools=["read_file"],
        )
        provider = _mock_provider("done")
        agent = LLMAgent(provider, [tool1, tool2], spec=spec)

        available = agent._get_tools()
        assert len(available) == 1
        assert available[0].name == "read_file"


class TestLLMAgentTrace:
    def test_trace_to_dict(self):
        """AgentTrace serialization works."""
        trace = AgentTrace(
            agent_name="test",
            task_description="test task",
            iterations=2,
            tool_calls_made=3,
            final_answer="result",
            completed=True,
        )
        d = trace.to_dict()

        assert d["agent_name"] == "test"
        assert d["iterations"] == 2
        assert d["tool_calls_made"] == 3
        assert d["completed"] is True

    def test_decision_to_dict(self):
        """AgentDecision serialization works."""
        decision = AgentDecision(
            decision_type=AgentDecisionType.COMPLETE,
            reasoning="Task done",
            final_answer="The answer",
            confidence=0.9,
        )
        d = decision.to_dict()

        assert d["decision_type"] == "complete"
        assert d["reasoning"] == "Task done"
        assert d["final_answer"] == "The answer"
        assert d["confidence"] == 0.9


class TestLLMAgentContext:
    def test_context_passed_to_prompt(self):
        """Agent includes context in the prompt."""
        provider = _mock_provider("I understand the context")
        agent = LLMAgent(provider, [])

        agent.run("do something", context={
            "goal": "Research Python",
            "previous_results": {"t1": "found data"},
        })

        call_args = provider.complete.call_args
        prompt = call_args[0][0]
        assert "Research Python" in prompt


class TestLLMAgentStructuredDecision:
    def test_json_decision_parsed(self):
        """Agent parses structured JSON decisions from LLM."""
        decision_json = json.dumps({
            "decision": "complete",
            "reasoning": "Found the answer",
            "final_answer": "Python is great",
            "confidence": 0.95,
        })
        provider = _mock_provider(decision_json)
        agent = LLMAgent(provider, [])

        trace = agent.run_with_trace("what is python?")

        assert trace.completed
        assert "Python is great" in trace.final_answer
        assert len(trace.decisions) == 1
        assert trace.decisions[0].confidence == 0.95

    def test_retry_decision_parsed(self):
        """Agent parses retry decisions."""
        decision_json = json.dumps({
            "decision": "retry",
            "reasoning": "First attempt failed",
            "confidence": 0.8,
        })
        tool = _mock_tool()
        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="test_tool", arguments={})]),
            decision_json,
        ])
        agent = LLMAgent(provider, [tool])

        trace = agent.run_with_trace("try this")

        assert len(trace.decisions) >= 1
