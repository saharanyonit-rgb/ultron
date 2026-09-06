"""Integration tests for JARVIS Phase 6.1: Production Runtime Integration.

Tests:
1. Simple chat
2. Goal creation
3. Goal execution
4. Tool execution
5. SSE event delivery
6. SSE duplicate prevention (pendingGoalId)
7. Backend health
8. Task status regression (_verify_completed_tasks)
9. Provider regression (gemini)
"""

import threading
import time
import json
import queue
from unittest.mock import MagicMock

import pytest

from ultron.config import load_config
from ultron.llm import build_provider
from ultron.tools import ToolRegistry
from ultron.tools.execution import ToolExecutor
from ultron.audit import AuditLogger
from ultron.status import StatusReporter
from ultron.agent_manager import AgentManager
from ultron.orchestrator import Orchestrator, OrchestratorConfig
from ultron.core.agent import Agent
from ultron.core.brain import Brain
from ultron.memory import Memory
from ultron.actions import PermissionGate
from ultron.task import Task, TaskGraph, TaskStatus
from ultron.web import JarvisAPI
from ultron.web_broadcaster import EventBroadcaster


class TestSSEEventDelivery:
    """Test SSE event delivery and handling."""

    def test_sse_event_broadcast_and_receive(self):
        """Test that events are broadcast and can be received."""
        broadcaster = EventBroadcaster()

        received_events = []
        q = broadcaster.subscribe()

        def listener():
            while True:
                try:
                    data = q.get(timeout=2)
                    received_events.append(data)
                except queue.Empty:
                    break

        thread = threading.Thread(target=listener, daemon=True)
        thread.start()

        broadcaster.broadcast("test_event", {"data": "test"})
        broadcaster.broadcast("another_event", {"value": 123})

        time.sleep(0.5)
        broadcaster.unsubscribe(q)

        assert len(received_events) == 2
        assert "test_event" in received_events[0]
        assert "another_event" in received_events[1]

    def test_sse_multiple_subscribers(self):
        """Test fan-out to multiple subscribers."""
        broadcaster = EventBroadcaster()

        q1 = broadcaster.subscribe()
        q2 = broadcaster.subscribe()

        received1 = []
        received2 = []

        def listener1():
            while True:
                try:
                    data = q1.get(timeout=2)
                    received1.append(data)
                except queue.Empty:
                    break

        def listener2():
            while True:
                try:
                    data = q2.get(timeout=2)
                    received2.append(data)
                except queue.Empty:
                    break

        t1 = threading.Thread(target=listener1, daemon=True)
        t2 = threading.Thread(target=listener2, daemon=True)
        t1.start()
        t2.start()

        broadcaster.broadcast("broadcast_event", {"test": True})

        time.sleep(0.5)
        broadcaster.unsubscribe(q1)
        broadcaster.unsubscribe(q2)

        assert len(received1) >= 1
        assert len(received2) >= 1


class TestBackendHealth:
    """Test backend health endpoint."""

    def test_health_endpoint_returns_status(self):
        """Test that health endpoint returns proper status."""
        config = load_config()
        provider = build_provider(config)
        registry = ToolRegistry()
        tool_executor = ToolExecutor(registry)
        from ultron.actions.audit_log import AuditLog
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jsonl') as f:
            audit = AuditLog(f.name)
        status = StatusReporter()
        agent_manager = AgentManager()

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            agent_manager=agent_manager,
            config=OrchestratorConfig(),
            audit_logger=AuditLogger(),
            status_reporter=status,
            autonomous_executor=None,
        )

        agent = Agent(
            provider=provider,
            tools=registry.all(),
            audit_log=audit,
            gate=PermissionGate(),
            max_iterations=config.max_tool_iterations,
        )
        brain = Brain(agent=agent, memory=Memory())

        web_server = JarvisAPI(
            host='127.0.0.1',
            port=8099,
            orchestrator=orchestrator,
            brain=brain,
        )

        thread = threading.Thread(target=web_server.serve_forever, daemon=True)
        thread.start()
        time.sleep(1)

        try:
            import requests
            r = requests.get('http://127.0.0.1:8099/api/status', timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert 'status' in data
            assert data['status'] == 'running'
            assert 'provider' in data
            assert data['provider'] == config.provider
        finally:
            web_server.shutdown()


class TestTaskStatusRegression:
    """Test that _verify_completed_tasks properly restores COMPLETED status."""

    def test_verified_task_remains_completed(self):
        """Regression test: verified tasks must remain COMPLETED, not RUNNING."""
        from ultron.orchestrator import Orchestrator
        from ultron.task import Task, TaskStatus
        from ultron.verification_v5 import VerificationEngine, VerificationCheckType

        config = OrchestratorConfig(enable_verification=True)
        registry = ToolRegistry()
        tool_executor = ToolExecutor(registry)
        audit = AuditLogger()
        status = StatusReporter()

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=config,
            audit_logger=audit,
            status_reporter=status,
        )

        goal = MagicMock()
        goal.id = "test-goal"

        task = Task(
            id="test-task",
            description="Test task",
            status=TaskStatus.COMPLETED,
            verification_criteria="task completed successfully",
        )

        graph = MagicMock()
        graph.get_tasks_by_status.return_value = [task]

        results = orchestrator._verify_completed_tasks(goal, graph)

        assert task.status == TaskStatus.COMPLETED
        assert results.get("test-task") is not None

    def test_task_without_verification_criteria_skipped(self):
        """Tasks without verification criteria should not be modified."""
        from ultron.orchestrator import Orchestrator
        from ultron.task import Task, TaskStatus

        config = OrchestratorConfig(enable_verification=True)
        registry = ToolRegistry()
        tool_executor = ToolExecutor(registry)
        audit = AuditLogger()
        status = StatusReporter()

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=config,
            audit_logger=audit,
            status_reporter=status,
        )

        goal = MagicMock()
        task = Task(
            id="test-task-no-verify",
            description="Task without verification",
            status=TaskStatus.COMPLETED,
        )

        graph = MagicMock()
        graph.get_tasks_by_status.return_value = [task]

        results = orchestrator._verify_completed_tasks(goal, graph)

        assert task.status == TaskStatus.COMPLETED
        assert "test-task-no-verify" not in results


class TestProviderRegression:
    """Test that provider configuration works correctly."""

    def test_gemini_provider_configured(self):
        """Test that gemini provider is properly configured."""
        import os

        os.environ['ULTRON_PROVIDER'] = 'gemini'

        config = load_config()
        assert config.provider == 'gemini'

        provider = build_provider(config)
        assert provider is not None

    def test_provider_respects_env_variable(self):
        """Test that provider is read from environment."""
        import os

        os.environ['ULTRON_PROVIDER'] = 'gemini'

        config = load_config()
        assert config.provider == 'gemini'


class TestGoalExecution:
    """Test goal execution through orchestrator."""

    def test_simple_goal_execution(self):
        """Test that a simple goal executes successfully."""
        from ultron.orchestrator import Orchestrator, OrchestratorConfig
        from ultron.tools import ToolRegistry
        from ultron.tools.execution import ToolExecutor
        from ultron.audit import AuditLogger
        from ultron.status import StatusReporter
        from ultron.agent_manager import AgentManager

        config = load_config()
        provider = build_provider(config)
        registry = ToolRegistry()
        tool_executor = ToolExecutor(registry)
        audit = AuditLogger()
        status = StatusReporter()
        agent_manager = AgentManager()

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            agent_manager=agent_manager,
            config=OrchestratorConfig(),
            audit_logger=audit,
            status_reporter=status,
            autonomous_executor=None,
        )

        result = orchestrator.execute_goal("Say hello")

        assert result is not None
        assert result.goal_result is not None
        assert result.state is not None


class TestToolExecution:
    """Test tool execution through the executor."""

    def test_get_system_info_tool(self):
        """Test that get_system_info tool executes correctly."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        result = executor.execute("get_system_info", {})

        assert result.status.value == "success"
        assert result.output is not None
        assert "os" in result.output

    def test_tool_not_found(self):
        """Test that appropriate error is returned for unknown tool."""
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        result = executor.execute("nonexistent_tool", {})

        assert result.status.value == "failure"
        assert "unknown tool" in result.error.lower()


class TestSSEEventTypes:
    """Test that all expected SSE event types are emitted."""

    def test_status_events_exist(self):
        """Test that all status events are defined."""
        from ultron.status import StatusEvent

        required_events = [
            "task_started",
            "planning",
            "plan_created",
            "agent_selected",
            "step_started",
            "step_completed",
            "step_failed",
            "verifying",
            "verified",
            "retrying",
            "recovering",
            "replaning",
            "completed",
            "failed",
            "error",
        ]

        for event_name in required_events:
            assert hasattr(StatusEvent, event_name.upper()), f"Missing StatusEvent.{event_name.upper()}"

    def test_status_reporter_has_methods(self):
        """Test that StatusReporter has all required methods."""
        from ultron.status import StatusReporter

        reporter = StatusReporter()

        required_methods = [
            "task_started",
            "planning",
            "plan_created",
            "agent_selected",
            "step_started",
            "step_completed",
            "step_failed",
            "verifying",
            "verified",
            "retrying",
            "recovering",
            "replaning",
            "completed",
            "failed",
        ]

        for method_name in required_methods:
            assert hasattr(reporter, method_name), f"Missing StatusReporter.{method_name}()"
            assert callable(getattr(reporter, method_name)), f"StatusReporter.{method_name} is not callable"


class TestPermissionManager:
    """Test the PermissionManager for web UI."""

    def test_permission_manager_creation(self):
        """Test that PermissionManager can be created."""
        from ultron.permission_manager import PermissionManager, redact_sensitive

        pm = PermissionManager()
        assert pm is not None
        assert hasattr(pm, 'request_permission')
        assert hasattr(pm, 'decide')
        assert hasattr(pm, 'list_pending')

    def test_permission_manager_decision(self):
        """Test that a permission can be submitted."""
        from ultron.permission_manager import PermissionManager

        pm = PermissionManager()

        # Submit a decision
        result = pm.decide("test-perm-123", True)
        # Should return False since the permission doesn't exist
        assert result is False

    def test_permission_manager_list_pending_empty(self):
        """Test that list_pending returns empty initially."""
        from ultron.permission_manager import PermissionManager

        pm = PermissionManager()
        pending = pm.list_pending()
        assert pending == []

    def test_redact_sensitive(self):
        """Test that sensitive information is redacted."""
        from ultron.permission_manager import redact_sensitive

        args = {
            "path": "/some/path",
            "api_key": "secret123",
            "content": "hello world",
            "password": "supersecret",
        }

        redacted = redact_sensitive(args)

        assert redacted["path"] == "/some/path"
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["content"] == "hello world"
        assert redacted["password"] == "***REDACTED***"

    def test_redact_sensitive_nested(self):
        """Test nested dict redaction."""
        from ultron.permission_manager import redact_sensitive

        args = {
            "outer": {
                "inner": "value",
                "secret_token": "abc123",
            }
        }

        redacted = redact_sensitive(args)

        assert redacted["outer"]["inner"] == "value"
        assert redacted["outer"]["secret_token"] == "***REDACTED***"

    def test_permission_manager_get_pending_not_found(self):
        """Test that get_pending returns None for unknown ID."""
        from ultron.permission_manager import PermissionManager

        pm = PermissionManager()
        pending = pm.get_pending("nonexistent-id")
        assert pending is None

    def test_permission_event_broadcast(self):
        """Test that permission events are properly structured."""
        from ultron.permission_manager import PermissionManager
        from ultron.web_broadcaster import EventBroadcaster
        from ultron.risk import RiskLevel
        import threading
        import queue

        broadcaster = EventBroadcaster()
        pm = PermissionManager(broadcaster=broadcaster)

        q = broadcaster.subscribe()

        # Simulate a permission request (would normally block)
        # But we can check the event structure by listening
        broadcaster.broadcast("permission_required", {
            "permission_id": "test-123",
            "tool": "create_file",
            "risk": "MEDIUM",
            "reason": "Test reason",
            "arguments": {"path": "/tmp/test.txt"},
            "created_at": 1234567890.0,
        })

        try:
            event = q.get(timeout=2)
            assert "permission_required" in event
            assert "test-123" in event
        except queue.Empty:
            pytest.fail("No event received")

        broadcaster.unsubscribe(q)


class TestPermissionAPI:
    """Test permission API endpoints."""

    def test_permission_endpoints_exist(self):
        """Test that permission API endpoints can be called."""
        import requests
        import threading
        import time

        from ultron.web import JarvisAPI
        from ultron.orchestrator import Orchestrator, OrchestratorConfig
        from ultron.tools import ToolRegistry
        from ultron.tools.execution import ToolExecutor
        from ultron.audit import AuditLogger
        from ultron.status import StatusReporter
        from ultron.agent_manager import AgentManager

        config = load_config()
        provider = build_provider(config)
        registry = ToolRegistry()
        tool_executor = ToolExecutor(registry)
        audit = AuditLogger()
        status = StatusReporter()
        agent_manager = AgentManager()

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            agent_manager=agent_manager,
            config=OrchestratorConfig(),
            audit_logger=audit,
            status_reporter=status,
            autonomous_executor=None,
        )

        web_server = JarvisAPI(
            host='127.0.0.1',
            port=8097,
            orchestrator=orchestrator,
            brain=None,
        )

        thread = threading.Thread(target=web_server.serve_forever, daemon=True)
        thread.start()
        time.sleep(1)

        try:
            # Test GET /api/permissions - should return empty list
            r = requests.get('http://127.0.0.1:8097/api/permissions', timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert 'pending' in data

            # Test POST /api/permissions/nonexistent/allow - should return 404
            r = requests.post('http://127.0.0.1:8097/api/permissions/nonexistent-id/allow', timeout=5)
            assert r.status_code == 404

        finally:
            web_server.shutdown()


class TestPermissionIntegration:
    """Integration tests for permission flow."""

    def test_permission_redaction_in_event(self):
        """Test that secrets are redacted when permission events are emitted."""
        from ultron.permission_manager import redact_sensitive

        # Simulate tool arguments with secrets
        args = {
            "command": "echo hello",
            "api_key": "sk-secret-key-12345",
            "password": "my_password",
            "token": "oauth-token-xyz",
        }

        redacted = redact_sensitive(args)

        # Verify redaction
        assert redacted["command"] == "echo hello"
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["password"] == "***REDACTED***"
        assert redacted["token"] == "***REDACTED***"

        # Verify no actual secrets leaked
        redacted_str = str(redacted)
        assert "sk-secret-key" not in redacted_str
        assert "my_password" not in redacted_str
        assert "oauth-token" not in redacted_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
