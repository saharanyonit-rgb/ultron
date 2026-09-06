"""Integration tests for Phase 4 features."""

from __future__ import annotations

from ultron.audit import AuditLogger, EventType
from ultron.browser import BrowserTool, MockBrowserSession
from ultron.execution_state import ExecutionStateStore, StepState, TaskState, TaskStatus
from ultron.policy import PolicyAction, PolicyEngine
from ultron.recovery import RecoveryEngine
from ultron.risk import RiskClassifier, RiskLevel
from ultron.sandbox import LocalSandbox
from ultron.status import StatusReporter, StatusEvent, CallbackSubscriber
from ultron.tools.command import CommandExecutor
from ultron.tools.filesystem import FilesystemTool


def test_agent_tool_permission_execution_verification(tmp_path):
    """Test: Agent → Tool → Permission → Execution → Verification"""
    # Setup
    fs = FilesystemTool(allowed_roots=[tmp_path])
    classifier = RiskClassifier()
    policy = PolicyEngine(confirm_callback=lambda t, a, r: True)

    # Agent requests tool
    tool_name = "create_file"
    risk = classifier.classify(tool_name)

    # Permission check
    allowed = policy.request_permission(tool_name, risk)
    assert allowed is True

    # Execute
    result = fs.create_file(tmp_path / "test.txt", "content")
    assert result["created"] is True

    # Verify
    read_result = fs.read_file(tmp_path / "test.txt")
    assert read_result["content"] == "content"


def test_planner_pipeline_agent_tool_recovery_verification(tmp_path):
    """Test: Planner → Pipeline → Agent → Tool → Recovery → Verification"""
    # Setup
    fs = FilesystemTool(allowed_roots=[tmp_path])
    recovery = RecoveryEngine(max_retries=2)
    audit = AuditLogger()

    # Create task with steps
    task = TaskState(task_id="t1", description="test task")
    step1 = StepState(step_id="s1", objective="create file")
    step2 = StepState(step_id="s2", objective="read file")
    task.steps = [step1, step2]

    # Execute step 1
    step1.status = "running"
    result1 = fs.create_file(tmp_path / "test.txt", "hello")
    step1.status = "succeeded"
    step1.result = result1

    # Execute step 2
    step2.status = "running"
    result2 = fs.read_file(tmp_path / "test.txt")
    step2.status = "succeeded"
    step2.result = result2

    # Verify
    assert len(task.completed_steps) == 2
    assert task.progress == 1.0

    # Audit
    audit.log_tool_executed("r1", "create_file", True, 10)
    audit.log_tool_executed("r1", "read_file", True, 5)
    assert len(audit.events) == 2


def test_sandbox_filesystem_integration(tmp_path):
    """Test: Sandbox → Filesystem → Verification"""
    with LocalSandbox() as sandbox:
        # Create file in sandbox workspace
        workspace = sandbox.get_workspace()
        fs = FilesystemTool(allowed_roots=[workspace])

        result = fs.create_file(workspace / "test.txt", "sandbox content")
        assert result["created"] is True

        # Read back
        read_result = fs.read_file(workspace / "test.txt")
        assert read_result["content"] == "sandbox content"


def test_browser_permission_integration():
    """Test: Browser → Permission → Execution"""
    browser = BrowserTool()
    policy = PolicyEngine(confirm_callback=lambda t, a, r: True)

    # Navigate (low risk, should be allowed)
    from ultron.browser import BrowserAction
    risk = browser.get_risk_level(BrowserAction.NAVIGATE)
    allowed = policy.request_permission("browser_navigate", risk)
    assert allowed is True

    result = browser.navigate("https://example.com")
    assert result.success is True

    # Read page
    read_result = browser.read_page()
    assert read_result.success is True


def test_execution_state_recovery_integration(tmp_path):
    """Test: Execution State → Recovery → Replanning"""
    store = ExecutionStateStore(tmp_path / "state.json")
    recovery = RecoveryEngine(max_retries=2)

    # Create task
    task = TaskState(task_id="t1", description="test")
    step = StepState(step_id="s1", objective="do something")
    task.steps = [step]
    store.save_task(task)

    # Simulate failure
    step.status = "failed"
    step.error = "timeout"
    step.retry_count = 0
    store.update_step("t1", "s1", "failed", error="timeout")

    # Recovery
    decision = recovery.decide_recovery(step, TimeoutError("timeout"))
    assert decision.action.value == "retry"

    # Retry
    result = recovery.execute_recovery(task, step, TimeoutError("timeout"))
    assert step.retry_count == 1
    assert step.status == "pending"

    # Persist
    store.save_task(task)
    loaded = store.load_task("t1")
    assert loaded.steps[0].retry_count == 1


def test_status_streaming_integration():
    """Test: Status → Streaming → Observation"""
    reporter = StatusReporter()
    events = []
    reporter.subscribe(CallbackSubscriber(lambda u: events.append(u)))

    reporter.task_started("t1", "test task")
    reporter.planning("t1")
    reporter.plan_created("t1", 3)
    reporter.agent_selected("t1", "research")
    reporter.step_started("t1", "s1", "step 1", 0.33)
    reporter.step_completed("t1", "s1", 0.33)
    reporter.completed("t1")

    assert len(events) == 7
    assert events[-1].event == StatusEvent.COMPLETED
    assert events[-1].progress == 1.0
