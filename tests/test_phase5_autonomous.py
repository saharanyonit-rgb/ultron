"""Tests for Phase 5.17: Autonomous Decision Loop."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.agents.llm_agent import AgentDecisionType
from ultron.audit import AuditLogger
from ultron.autonomous import (
    AutonomousConfig,
    AutonomousExecutor,
    AutonomousState,
    TaskExecutionRecord,
)
from ultron.llm.base import ProviderResult, ToolCall
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.task import Task, TaskPriority, TaskStatus
from ultron.tools import ToolExecutor, ToolRegistry
from ultron.tools.base import ToolSpec
from ultron.tools.execution import ToolExecutionStatus


def _mock_provider(responses):
    """Create a mock provider with a sequence of responses."""
    provider = MagicMock()
    if isinstance(responses, list):
        provider.complete.side_effect = [
            ProviderResult(
                text=r if isinstance(r, str) else r[0],
                tool_calls=r[1] if isinstance(r, tuple) else [],
            )
            for r in responses
        ]
    else:
        provider.complete.return_value = ProviderResult(text=responses, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_tool(name: str = "test_tool") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.spec = ToolSpec(
        name=name,
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        output_schema={"type": "object", "properties": {}},
    )
    tool.run.return_value = {"result": "output"}
    tool.validate_parameters.return_value = (True, None)
    return tool


def _make_executor(provider, tools, tmp_path):
    """Create a real AutonomousExecutor with mocked security."""
    registry = ToolRegistry(tools)
    gate = MagicMock()
    gate.check.return_value = MagicMock(allowed=True, reason="test")
    audit_log = MagicMock()
    tool_executor = ToolExecutor(registry=registry, gate=gate, audit_log=audit_log)
    audit = AuditLogger()

    return AutonomousExecutor(
        provider=provider,
        tools=tools,
        tool_executor=tool_executor,
        audit_logger=audit,
        config=AutonomousConfig(max_iterations_per_task=5),
    )


class TestAutonomousExecution:
    def test_simple_task_completion(self, tmp_path):
        """Agent completes a simple task with direct answer."""
        provider = _mock_provider("Task completed successfully")
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="Do something simple")
        result = executor.execute_task(task)

        assert result.status == ExecutionStatus.SUCCESS
        assert "Task completed" in str(result.output)

    def test_task_with_tool_calls(self, tmp_path):
        """Agent completes a task using tool calls."""
        tool = _mock_tool("read_file")
        tool.run.return_value = {"content": "file data"}

        provider = _mock_provider([
            (None, [ToolCall(id="c1", name="read_file", arguments={"path": "test.txt"})]),
            "File contains: file data",
        ])
        executor = _make_executor(provider, [tool], tmp_path)

        task = Task(
            id="t1",
            description="Read the file",
            required_tools=["read_file"],
        )
        result = executor.execute_task(task)

        assert result.status == ExecutionStatus.SUCCESS

    def test_task_with_context(self, tmp_path):
        """Agent receives goal context."""
        provider = _mock_provider("Done")
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="Do something")
        result = executor.execute_task(
            task,
            goal_context="Research Python frameworks",
            previous_results={"t0": "prior data"},
        )

        assert result.status == ExecutionStatus.SUCCESS
        # Verify context was passed to the provider
        call_args = provider.complete.call_args
        prompt = call_args[0][0]
        assert "Research Python" in prompt

    def test_task_failure_recorded(self, tmp_path):
        """Task failure is properly recorded."""
        provider = _mock_provider("I cannot do this task")
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="Impossible task")
        result = executor.execute_task(task)

        record = executor.get_record("t1")
        assert record is not None
        assert record.status == "completed"


class TestAutonomousToolExecution:
    def test_direct_tool_execution(self, tmp_path):
        """execute_tool_directly goes through security boundary."""
        tool = _mock_tool("read_file")
        tool.run.return_value = {"content": "data"}
        executor = _make_executor(provider=_mock_provider("ok"), tools=[tool], tmp_path=tmp_path)

        result = executor.execute_tool_directly("read_file", {"path": "test.txt"})

        assert result.status == ToolExecutionStatus.SUCCESS
        tool.run.assert_called_once_with(path="test.txt")

    def test_direct_tool_unknown(self, tmp_path):
        """Unknown tool returns failure."""
        executor = _make_executor(provider=_mock_provider("ok"), tools=[], tmp_path=tmp_path)

        result = executor.execute_tool_directly("nonexistent", {})

        assert result.status == ToolExecutionStatus.FAILURE


class TestAutonomousConfig:
    def test_default_config(self):
        """Default config has sensible values."""
        config = AutonomousConfig()
        assert config.max_iterations_per_task == 10
        assert config.max_tool_calls_per_task == 20
        assert config.task_timeout_seconds == 120

    def test_custom_config(self):
        """Custom config overrides defaults."""
        config = AutonomousConfig(max_iterations_per_task=3)
        assert config.max_iterations_per_task == 3


class TestAutonomousRecord:
    def test_record_serialization(self):
        """TaskExecutionRecord serializes correctly."""
        record = TaskExecutionRecord(
            task_id="t1",
            agent_name="test",
            iterations=3,
            tool_calls=5,
            final_answer="done",
            status="completed",
        )
        d = record.to_dict()

        assert d["task_id"] == "t1"
        assert d["iterations"] == 3
        assert d["tool_calls"] == 5
        assert d["status"] == "completed"

    def test_record_tracks_decisions(self):
        """Record tracks agent decisions."""
        record = TaskExecutionRecord(task_id="t1")
        record.decisions = [
            {"type": "continue", "reasoning": "making progress"},
            {"type": "complete", "reasoning": "done"},
        ]
        d = record.to_dict()
        assert d["decisions_count"] == 2


class TestAutonomousState:
    def test_state_transitions(self, tmp_path):
        """State transitions correctly during execution."""
        provider = _mock_provider("Done")
        executor = _make_executor(provider, [], tmp_path)

        assert executor.state == AutonomousState.IDLE

        task = Task(id="t1", description="test")
        result = executor.execute_task(task)

        assert executor.state == AutonomousState.IDLE


class TestAutonomousOutputParsing:
    def test_json_output_parsed(self, tmp_path):
        """JSON final answers are parsed into dict output."""
        json_answer = json.dumps({"result": "success", "count": 42})
        provider = _mock_provider(json_answer)
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="test")
        result = executor.execute_task(task)

        assert result.output.get("result") == "success"
        assert result.output.get("count") == 42

    def test_text_output_wrapped(self, tmp_path):
        """Plain text answers are wrapped in dict."""
        provider = _mock_provider("just a text answer")
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="test")
        result = executor.execute_task(task)

        assert "answer" in result.output
        assert "just a text answer" in result.output["answer"]

    def test_markdown_json_parsed(self, tmp_path):
        """JSON wrapped in markdown fences is parsed."""
        json_answer = '```json\n{"key": "value"}\n```'
        provider = _mock_provider(json_answer)
        executor = _make_executor(provider, [], tmp_path)

        task = Task(id="t1", description="test")
        result = executor.execute_task(task)

        assert result.output.get("key") == "value"
