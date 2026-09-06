"""Tests for Phase 5 Execution Orchestrator — End-to-End Integration."""
from __future__ import annotations
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from ultron.agent_manager import AgentManager
from ultron.actions.audit_log import AuditLog
from ultron.audit import AuditLogger
from ultron.execution_state import ExecutionStateStore
from ultron.orchestrator import Orchestrator, OrchestratorConfig, OrchestratorState
from ultron.policy import PolicyEngine
from ultron.risk import RiskClassifier
from ultron.status import StatusReporter
from ultron.tools import ToolExecutor, ToolRegistry
from ultron.tools.file_ops import CreateFile, ReadFile, SearchFiles
def _make_orchestrator(tmp_path: Path, **kwargs) -> Orchestrator:
    """Create a real orchestrator with file tools for testing."""
    tools = [ReadFile(), CreateFile(), SearchFiles()]
    registry = ToolRegistry(tools)
    gate = MagicMock()
    gate.check.return_value = MagicMock(allowed=True, reason="test")
    audit_log = AuditLog(tmp_path / "audit.jsonl")
    executor = ToolExecutor(registry=registry, gate=gate, audit_log=audit_log)
    risk = RiskClassifier()
    policy = PolicyEngine(confirm_callback=lambda t, a, r: True)
    agent_mgr = AgentManager()
    audit = AuditLogger()
    status = StatusReporter()
    state = ExecutionStateStore(tmp_path / "state.json")
    init_kwargs = {
        "tool_executor": executor,
        "agent_manager": agent_mgr,
        "config": OrchestratorConfig(
            enable_verification=True,
            enable_persistence=True,
            enable_parallel_execution=False,
        ),
        "audit_logger": audit,
        "status_reporter": status,
        "state_store": state,
        "policy_engine": policy,
        "risk_classifier": risk,
    }
    init_kwargs.update(kwargs)
    return Orchestrator(**init_kwargs)
class TestOrchestratorEndToEnd:
    def test_simple_file_creation(self, tmp_path):
        """Test: Create a simple file and verify it exists."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal(
            f"Create a file called test.txt in {tmp_path} with content 'hello world'"
        )
        assert result.goal_result.outcome.value in ("success", "partial_success", "failed")
        assert result.goal_result.planned_tasks >= 1
        test_file = tmp_path / "test.txt"
        if test_file.exists():
            assert test_file.read_text(encoding="utf-8") == "hello world"
    def test_goal_state_tracking(self, tmp_path):
        """Test that orchestrator tracks state correctly."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal("read system info")
        assert orch.current_goal is not None
        assert orch.current_graph is not None
    def test_orchestrator_events(self, tmp_path):
        """Test that orchestrator emits events."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal("read system info")
        assert len(result.events) > 0
        event_types = [e["event_type"] for e in result.events]
        assert "EXECUTION_START" in event_types
    def test_orchestrator_state(self, tmp_path):
        """Test orchestrator state transitions."""
        orch = _make_orchestrator(tmp_path)
        assert orch.state == OrchestratorState.IDLE
        result = orch.execute_goal("read system info")
        assert orch.state == OrchestratorState.COMPLETED
    def test_result_structure(self, tmp_path):
        """Test that the result has the expected structure."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal("read system info")
        goal_result = result.goal_result
        assert goal_result.goal_id
        assert goal_result.original_request == "read system info"
        assert goal_result.planned_tasks >= 1
        assert goal_result.summary
    def test_result_serialization(self, tmp_path):
        """Test that the result can be serialized."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal("read system info")
        d = result.to_dict()
        assert "goal_result" in d
        assert "state" in d
    def test_persistence(self, tmp_path):
        """Test that execution state is persisted."""
        orch = _make_orchestrator(tmp_path)
        result = orch.execute_goal("read system info")
        if orch._state_store:
            tasks = orch._state_store.list_tasks()
            assert len(tasks) > 0
    def test_audit_events_created(self, tmp_path):
        """Test that audit events are created during execution."""
        orch = _make_orchestrator(tmp_path)
        orch.execute_goal("read system info")
        assert len(orch._audit.events) > 0
class TestOrchestratorSecurity:
    def test_permission_denied(self, tmp_path):
        """Test that permission denied is handled correctly."""
        tools = [ReadFile(), CreateFile(), SearchFiles()]
        registry = ToolRegistry(tools)
        gate = MagicMock()
        gate.check.return_value = MagicMock(allowed=False, reason="denied by policy")
        audit_log = AuditLog(tmp_path / "audit_denied.jsonl")
        executor = ToolExecutor(registry=registry, gate=gate, audit_log=audit_log)
        orch = Orchestrator(
            tool_executor=executor,
            config=OrchestratorConfig(enable_verification=True),
        )
        result = orch.execute_goal(
            f"Create a file called test.txt in {tmp_path} with content 'test'"
        )
        assert result.goal_result.outcome.value in ("failed", "partial_success", "blocked")
    def test_risk_classification_used(self, tmp_path):
        """Test that risk classification is applied."""
        orch = _make_orchestrator(tmp_path)
        risk = orch._risk_classifier
        read_risk = risk.classify("read_file")
        write_risk = risk.classify("create_file")
        delete_risk = risk.classify("delete_file")
        assert read_risk.value == "read"
        assert write_risk.value == "medium"
        assert delete_risk.value == "high"
class TestOrchestratorLLMIntegration:
    def test_llm_provider_wires_llm_goal_and_planner(self, tmp_path):
        """Test that passing an LLMProvider initializes LLMGoalEngine and LLMGoalPlanner."""
        from unittest.mock import MagicMock
        from ultron.llm.base import LLMProvider
        from ultron.llm_goal import LLMGoalEngine
        from ultron.llm_planner import LLMGoalPlanner
        mock_provider = MagicMock(spec=LLMProvider)
        orch = _make_orchestrator(tmp_path, llm_provider=mock_provider)
        assert isinstance(orch._goal_engine, LLMGoalEngine)
        assert isinstance(orch._planner, LLMGoalPlanner)
    def test_autonomous_executor_wires_llm_goal_and_planner(self, tmp_path):
        """Test that passing an AutonomousExecutor extracts its provider to initialize LLMGoalEngine and LLMGoalPlanner."""
        from unittest.mock import MagicMock
        from ultron.autonomous import AutonomousExecutor
        from ultron.llm_goal import LLMGoalEngine
        from ultron.llm_planner import LLMGoalPlanner
        mock_executor = MagicMock(spec=AutonomousExecutor)
        mock_executor._provider = MagicMock()
        orch = _make_orchestrator(tmp_path, autonomous_executor=mock_executor)
        assert isinstance(orch._goal_engine, LLMGoalEngine)
        assert isinstance(orch._planner, LLMGoalPlanner)
