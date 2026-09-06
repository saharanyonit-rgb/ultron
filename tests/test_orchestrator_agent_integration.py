"""Tests for orchestrator-AutonomousExecutor integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ultron.agents.llm_agent import LLMAgent
from ultron.audit import AuditLogger
from ultron.autonomous import AutonomousExecutor, AutonomousConfig
from ultron.goal import Goal, GoalStatus
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.orchestrator import Orchestrator, OrchestratorConfig
from ultron.policy import PolicyEngine
from ultron.risk import RiskClassifier
from ultron.task import Task, TaskGraph
from ultron.tools import ToolExecutor, ToolExecutionResult, ToolExecutionStatus


def _mock_provider(text: str = "Done") -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_executor() -> MagicMock:
    executor = MagicMock()
    executor.execute.return_value = ToolExecutionResult(
        tool_name="test_tool",
        status=ToolExecutionStatus.SUCCESS,
        output={"result": "ok"},
    )
    return executor


# ═══════════════════════════════════════════════════════════════════
# LLMAgent: ToolExecutor Integration
# ═══════════════════════════════════════════════════════════════════

class TestLLMAgentToolExecutor:
    def test_agent_uses_tool_executor_when_provided(self):
        """When ToolExecutor is provided, tool calls route through it."""
        from ultron.tools.base import Tool

        class DummyTool(Tool):
            name = "dummy"
            description = "test"
            parameters = {"type": "object", "properties": {}}
            output_schema = {"type": "object", "properties": {}}

            def run(self, **kwargs):
                return {"direct": True}

        mock_exec = MagicMock()
        mock_exec.execute.return_value = ToolExecutionResult(
            tool_name="dummy",
            status=ToolExecutionStatus.SUCCESS,
            output={"via_executor": True},
        )

        # LLM returns a tool call, then completes
        provider = MagicMock()
        tool_call = MagicMock()
        tool_call.name = "dummy"
        tool_call.arguments = {}
        provider.complete.side_effect = [
            ProviderResult(text=None, tool_calls=[tool_call]),
            ProviderResult(text="Done", tool_calls=[]),
        ]

        agent = LLMAgent(
            provider=provider,
            tools=[DummyTool()],
            tool_executor=mock_exec,
        )
        trace = agent.run_with_trace("Do something")

        # Verify ToolExecutor was called, not tool.run() directly
        mock_exec.execute.assert_called_once_with("dummy", {})
        assert trace.completed is True

    def test_agent_falls_back_to_direct_when_no_executor(self):
        """Without ToolExecutor, agent calls tool.run() directly."""
        from ultron.tools.base import Tool

        class DummyTool(Tool):
            name = "dummy"
            description = "test"
            parameters = {"type": "object", "properties": {}}
            output_schema = {"type": "object", "properties": {}}

            def run(self, **kwargs):
                return {"direct": True}

        provider = MagicMock()
        tool_call = MagicMock()
        tool_call.name = "dummy"
        tool_call.arguments = {}
        provider.complete.side_effect = [
            ProviderResult(text=None, tool_calls=[tool_call]),
            ProviderResult(text="Done", tool_calls=[]),
        ]

        agent = LLMAgent(
            provider=provider,
            tools=[DummyTool()],
            tool_executor=None,
        )
        trace = agent.run_with_trace("Do something")
        assert trace.completed is True


# ═══════════════════════════════════════════════════════════════════
# Orchestrator: AutonomousExecutor Integration
# ═══════════════════════════════════════════════════════════════════

class TestOrchestratorAutonomousExecutor:
    def test_orchestrator_accepts_autonomous_executor(self):
        """Orchestrator can be created with an AutonomousExecutor."""
        executor = _mock_executor()
        provider = _mock_provider()
        tools = MagicMock()
        autonomous = AutonomousExecutor(
            provider=provider,
            tools=[],
            tool_executor=executor,
        )
        orch = Orchestrator(
            tool_executor=executor,
            autonomous_executor=autonomous,
        )
        assert orch._autonomous_executor is autonomous

    def test_orchestrator_uses_autonomous_when_available(self):
        """When AutonomousExecutor is provided, tasks route through it."""
        executor = _mock_executor()
        provider = _mock_provider()

        autonomous = MagicMock()
        autonomous.execute_task.return_value = ExecutionResult(
            tool_name="autonomous",
            status=ExecutionStatus.SUCCESS,
            output={"answer": "done"},
        )

        orch = Orchestrator(
            tool_executor=executor,
            autonomous_executor=autonomous,
        )
        orch._current_goal = Goal(
            id="g1",
            description="test goal",
            status=GoalStatus.EXECUTING,
        )
        orch._current_graph = TaskGraph(goal_id="g1", description="test")

        task = Task(
            id="t1",
            description="test task",
        )
        task.required_tools = ["read_file"]

        result = orch._execute_task_tools(task)

        # Verify autonomous executor was called
        autonomous.execute_task.assert_called_once()
        assert result.status == ExecutionStatus.SUCCESS

    def test_orchestrator_falls_back_without_autonomous(self):
        """Without AutonomousExecutor, tasks use direct tool dispatch."""
        executor = _mock_executor()
        orch = Orchestrator(tool_executor=executor)
        assert orch._autonomous_executor is None

        task = Task(
            id="t1",
            description="test task",
        )
        task.required_tools = ["read_file"]

        result = orch._execute_task_tools(task)
        # Should use direct dispatch
        executor.execute.assert_called_once()

    def test_autonomous_receives_goal_context(self):
        """AutonomousExecutor receives goal context for task execution."""
        executor = _mock_executor()
        provider = _mock_provider()

        autonomous = MagicMock()
        autonomous.execute_task.return_value = ExecutionResult(
            tool_name="autonomous",
            status=ExecutionStatus.SUCCESS,
            output={},
        )

        orch = Orchestrator(
            tool_executor=executor,
            autonomous_executor=autonomous,
        )
        goal = Goal(
            id="g1",
            description="Build a web scraper",
            status=GoalStatus.EXECUTING,
        )
        orch._current_goal = goal
        orch._current_graph = TaskGraph(goal_id="g1", description="test")

        task = Task(id="t1", description="scrape data")
        task.required_tools = ["read_file"]

        orch._execute_task_tools(task)

        # Verify goal context was passed
        call_kwargs = autonomous.execute_task.call_args
        assert call_kwargs[1]["goal_context"] == "Build a web scraper"

    def test_autonomous_config_max_iterations(self):
        """AutonomousConfig controls max iterations per task."""
        config = AutonomousConfig(max_iterations_per_task=5)
        assert config.max_iterations_per_task == 5

        executor = _mock_executor()
        provider = _mock_provider()
        autonomous = AutonomousExecutor(
            provider=provider,
            tools=[],
            tool_executor=executor,
            config=config,
        )
        assert autonomous._config.max_iterations_per_task == 5


# ═══════════════════════════════════════════════════════════════════
# Security Boundary Preservation
# ═══════════════════════════════════════════════════════════════════

class TestSecurityBoundaryPreserved:
    def test_autonomous_executor_uses_tool_executor(self):
        """AutonomousExecutor passes ToolExecutor to LLMAgent."""
        executor = _mock_executor()
        provider = _mock_provider()

        autonomous = AutonomousExecutor(
            provider=provider,
            tools=[],
            tool_executor=executor,
        )

        # Verify the tool executor is stored
        assert autonomous._tool_executor is executor
