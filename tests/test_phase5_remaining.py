"""Tests for Phases 5.22-5.30: Memory, Replanning, Resources, Credentials, Network, Execution Control, Observability, Multi-Goal, Integration."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

from ultron.credentials import CredentialManager
from ultron.execution_control import (
    ExecutionController,
    ExecutionGate,
    ExecutionState,
    RateLimitConfig,
)
from ultron.goal import Goal, GoalStatus, GoalComplexity
from ultron.integration_validator import IntegrationValidator
from ultron.llm.base import ProviderResult
from ultron.memory_manager import EpisodeRecord, MemoryEntry, MemoryManager, MemoryType
from ultron.models import ExecutionResult, ExecutionStatus, MultiStepPlan, MultiStepPlanStep
from ultron.multi_goal import GoalPriority, GoalScheduleStatus, MultiGoalManager
from ultron.network_security import (
    BrowserSecurityGuard,
    BrowserSandboxPolicy,
    NetworkPolicy,
    NetworkRequest,
    NetworkSecurityGuard,
)
from ultron.observability import MetricsCollector, SpanStatus, TraceCollector
from ultron.replanning import DynamicReplanner, ReplanTrigger
from ultron.resource_manager import BudgetConfig, ResourceManager, ResourceType
from ultron.tool_selection import ToolSelector
from ultron.uncertainty import ConfidenceLevel, UncertaintyHandler


def _mock_provider(text: str) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_provider_error() -> MagicMock:
    provider = MagicMock()
    provider.complete.side_effect = Exception("LLM error")
    provider.name = "mock"
    return provider


# ═══════════════════════════════════════════════════════════════════
# Phase 5.22: Memory System
# ═══════════════════════════════════════════════════════════════════

class TestWorkingMemory:
    def test_add_and_retrieve(self):
        mm = MemoryManager()
        mm.add_working("context A")
        mm.add_working("context B")
        working = mm.get_working(limit=2)
        assert len(working) == 2
        assert working[1].content == "context B"

    def test_bounded_limit(self):
        mm = MemoryManager(working_memory_limit=3)
        for i in range(5):
            mm.add_working(f"item {i}")
        working = mm.get_working(limit=10)
        assert len(working) == 3
        assert working[0].content == "item 2"

    def test_clear_working(self):
        mm = MemoryManager()
        mm.add_working("data")
        mm.clear_working()
        assert len(mm.get_working()) == 0


class TestEpisodicMemory:
    def test_store_and_retrieve(self):
        mm = MemoryManager()
        ep = EpisodeRecord(
            goal_id="g1",
            goal_description="Test goal",
            outcome="success",
            tasks_completed=3,
        )
        mm.store_episode(ep)
        episodes = mm.get_episodes()
        assert len(episodes) == 1
        assert episodes[0].goal_id == "g1"

    def test_filter_by_outcome(self):
        mm = MemoryManager()
        mm.store_episode(EpisodeRecord(goal_id="g1", outcome="success"))
        mm.store_episode(EpisodeRecord(goal_id="g2", outcome="failure"))
        success = mm.get_episodes(outcome="success")
        assert len(success) == 1

    def test_search_episodes(self):
        mm = MemoryManager()
        mm.store_episode(EpisodeRecord(
            goal_id="g1",
            goal_description="Python code analysis",
            strategies_used=["static_analysis"],
        ))
        mm.store_episode(EpisodeRecord(
            goal_id="g2",
            goal_description="File system operations",
            strategies_used=["file_read"],
        ))
        results = mm.search_episodes("Python analysis")
        assert len(results) >= 1
        assert results[0].goal_id == "g1"

    def test_bounded_limit(self):
        mm = MemoryManager(episodic_memory_limit=5)
        for i in range(8):
            mm.store_episode(EpisodeRecord(goal_id=f"g{i}"))
        assert len(mm.get_episodes()) == 5


class TestSemanticMemory:
    def test_add_and_search(self):
        mm = MemoryManager()
        mm.add_semantic("Python is a programming language")
        mm.add_semantic("JavaScript is used for web")
        results = mm.search_semantic("Python language")
        assert len(results) >= 1
        assert "Python" in results[0].content

    def test_importance_weighted(self):
        mm = MemoryManager()
        mm.add_semantic("low importance fact", importance=0.1)
        mm.add_semantic("high importance fact", importance=0.9)
        results = mm.search_semantic("importance fact")
        assert len(results) == 2
        assert results[0].importance >= results[1].importance


class TestProjectMemory:
    def test_add_and_get(self):
        mm = MemoryManager()
        mm.add_project("jarvis", "Phase 5 started")
        mm.add_project("jarvis", "Phase 5.14 complete")
        entries = mm.get_project("jarvis")
        assert len(entries) == 2

    def test_isolation(self):
        mm = MemoryManager()
        mm.add_project("project_a", "data A")
        mm.add_project("project_b", "data B")
        assert len(mm.get_project("project_a")) == 1
        assert len(mm.get_project("project_b")) == 1


class TestMemoryContext:
    def test_build_context(self):
        mm = MemoryManager()
        mm.add_working("current task")
        mm.add_semantic("relevant fact")
        mm.store_episode(EpisodeRecord(
            goal_id="g1",
            outcome="success",
            goal_description="related goal",
        ))
        context = mm.build_context_for_goal("related goal")
        assert len(context) > 0

    def test_stats(self):
        mm = MemoryManager()
        mm.add_working("w")
        mm.add_semantic("s")
        mm.store_episode(EpisodeRecord(goal_id="g", outcome="ok"))
        stats = mm.get_stats()
        assert stats["working"] == 1
        assert stats["episodic"] == 1
        assert stats["semantic"] == 1

    def test_serialization(self):
        entry = MemoryEntry(content="test", memory_type=MemoryType.WORKING.value)
        d = entry.to_dict()
        assert d["content"] == "test"
        restored = MemoryEntry.from_dict(d)
        assert restored.content == "test"


class TestMemoryPersistence:
    def test_persist_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "memory.json"
            mm1 = MemoryManager(persistence_path=path)
            mm1.store_episode(EpisodeRecord(goal_id="g1", outcome="success"))
            mm1.add_semantic("Python is a language")

            mm2 = MemoryManager(persistence_path=path)
            assert len(mm2.get_episodes()) == 1
            # Verify semantic memory was persisted
            stats = mm2.get_stats()
            assert stats["semantic"] == 1


class TestReplanDetection:
    def test_no_failure_no_replan(self):
        replanner = DynamicReplanner()
        results = {
            "t1": ExecutionResult(tool_name="a", status=ExecutionStatus.SUCCESS, output={}),
        }
        trigger = replanner.should_replan(results, total_tasks=1)
        assert trigger.reason == "no_replan_needed"

    def test_failure_triggers_replan(self):
        replanner = DynamicReplanner(failure_threshold=1)
        results = {
            "t1": ExecutionResult(tool_name="a", status=ExecutionStatus.FAILED, output={}),
        }
        trigger = replanner.should_replan(results, total_tasks=2)
        assert "failed" in trigger.reason.lower()
        assert "t1" in trigger.failed_tasks


class TestReplanExecution:
    def test_heuristic_replan(self):
        replanner = DynamicReplanner()
        plan = MultiStepPlan(
            description="test",
            steps=[
                MultiStepPlanStep(step_id="t1", tool_name="a", description="step 1"),
                MultiStepPlanStep(step_id="t2", tool_name="b", description="step 2"),
            ],
        )
        trigger = ReplanTrigger(
            reason="t1 failed",
            failed_tasks=["t1"],
        )
        result = replanner.replan(plan, trigger, "test objective")
        assert result.success is True
        assert result.new_plan is not None

    def test_llm_replan(self):
        plan_json = json.dumps({
            "steps": [
                {"task_id": "t_new", "tool": "b", "description": "new approach"},
            ],
            "reasoning": "Replaced failed step",
            "changes": ["Removed t1", "Added t_new"],
        })
        provider = _mock_provider(plan_json)
        replanner = DynamicReplanner(provider=provider)
        plan = MultiStepPlan(
            description="test",
            steps=[
                MultiStepPlanStep(step_id="t1", tool_name="a", description="step 1"),
                MultiStepPlanStep(step_id="t2", tool_name="b", description="step 2"),
            ],
        )
        trigger = ReplanTrigger(reason="t1 failed", failed_tasks=["t1"])
        result = replanner.replan(plan, trigger, "test objective")
        assert result.success is True

    def test_max_replans_respected(self):
        replanner = DynamicReplanner(max_replans=2)
        plan = MultiStepPlan(
            description="test",
            steps=[MultiStepPlanStep(step_id="t1", tool_name="a", description="step")],
        )
        trigger = ReplanTrigger(reason="fail", failed_tasks=["t1"])
        replanner.replan(plan, trigger, "obj")
        replanner.replan(plan, trigger, "obj")
        result = replanner.replan(plan, trigger, "obj")
        assert result.success is False

    def test_no_replan_needed(self):
        replanner = DynamicReplanner()
        plan = MultiStepPlan(
            description="test",
            steps=[MultiStepPlanStep(step_id="t1", tool_name="a", description="step")],
        )
        trigger = ReplanTrigger(reason="no_replan_needed")
        result = replanner.replan(plan, trigger, "obj")
        assert result.success is True
        assert result.new_plan == plan


# ═══════════════════════════════════════════════════════════════════
# Phase 5.24: Resource & Budget Management
# ═══════════════════════════════════════════════════════════════════

class TestBudgetTracking:
    def test_record_api_calls(self):
        rm = ResourceManager(BudgetConfig(max_api_calls=10))
        rm.record_api_call(tokens=100, cost_usd=0.01)
        assert rm.usage.api_calls == 1
        assert rm.usage.tokens == 100
        assert rm.usage.cost_usd == 0.01

    def test_can_proceed(self):
        rm = ResourceManager(BudgetConfig(max_api_calls=5))
        for _ in range(4):
            rm.record_api_call()
        assert rm.check_can_proceed() is True
        rm.record_api_call()
        assert rm.check_can_proceed() is False

    def test_remaining_budget(self):
        rm = ResourceManager(BudgetConfig(max_api_calls=10, max_tokens=1000))
        rm.record_api_call(tokens=200)
        remaining = rm.get_remaining_budget()
        assert remaining["api_calls"] == 9
        assert remaining["tokens"] == 800

    def test_usage_percentage(self):
        rm = ResourceManager(BudgetConfig(max_api_calls=100))
        for _ in range(50):
            rm.record_api_call()
        pct = rm.get_usage_percentage()
        assert pct["api_calls"] == 50.0

    def test_cost_estimation(self):
        rm = ResourceManager()
        cost = rm.estimate_llm_cost(1000, 500, "gpt-4")
        assert cost > 0

    def test_checkpoint(self):
        rm = ResourceManager()
        rm.record_api_call()
        cp = rm.checkpoint("step1")
        assert cp["label"] == "step1"
        assert len(rm.get_checkpoints()) == 1

    def test_reset(self):
        rm = ResourceManager()
        rm.record_api_call()
        rm.reset()
        assert rm.usage.api_calls == 0

    def test_warnings(self):
        rm = ResourceManager(BudgetConfig(max_api_calls=10))
        for _ in range(10):
            rm.record_api_call()
        assert len(rm.get_warnings()) > 0


# ═══════════════════════════════════════════════════════════════════
# Phase 5.25: Credential Management
# ═══════════════════════════════════════════════════════════════════

class TestCredentialStorage:
    def test_store_and_retrieve(self):
        cm = CredentialManager()
        cm.store("api_key", "secret_abc123xyz", service="openai")
        value = cm.retrieve("api_key")
        assert value == "secret_abc123xyz"

    def test_list_credentials(self):
        cm = CredentialManager()
        cm.store("key1", "val1", service="s1")
        cm.store("key2", "val2", service="s2")
        all_creds = cm.list_credentials()
        assert len(all_creds) == 2

    def test_list_by_service(self):
        cm = CredentialManager()
        cm.store("key1", "val1", service="s1")
        cm.store("key2", "val2", service="s2")
        s1_creds = cm.list_credentials(service="s1")
        assert len(s1_creds) == 1

    def test_delete(self):
        cm = CredentialManager()
        cm.store("key", "val")
        assert cm.delete("key") is True
        assert cm.retrieve("key") is None

    def test_metadata_no_values(self):
        cm = CredentialManager()
        cm.store("key", "super_secret")
        d = cm.to_dict()
        assert "super_secret" not in json.dumps(d)


class TestCredentialSanitization:
    def test_sanitize_known_values(self):
        cm = CredentialManager()
        cm.store("key", "my_secret_token_value_12345")
        text = "The key is my_secret_token_value_12345 in config"
        sanitized = cm.sanitize_text(text)
        assert "my_secret_token_value_12345" not in sanitized
        assert "REDACTED" in sanitized

    def test_detect_secrets(self):
        cm = CredentialManager()
        findings = cm.detect_secrets("api_key=sk_1234567890abcdef12345678")
        assert len(findings) > 0

    def test_detect_private_key(self):
        cm = CredentialManager()
        findings = cm.detect_secrets("-----BEGIN RSA PRIVATE KEY-----")
        assert len(findings) > 0


# ═══════════════════════════════════════════════════════════════════
# Phase 5.26: Network/Browser Security
# ═══════════════════════════════════════════════════════════════════

class TestNetworkSecurity:
    def test_https_allowed(self):
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        verdict = guard.validate_url("https://api.openai.com/v1")
        assert verdict.allowed is True

    def test_http_blocked(self):
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        verdict = guard.validate_url("http://api.openai.com/v1")
        assert verdict.allowed is False

    def test_domain_blocked(self):
        policy = NetworkPolicy(blocked_domains=["evil.com"])
        guard = NetworkSecurityGuard(policy)
        verdict = guard.validate_url("https://evil.com/steal")
        assert verdict.allowed is False

    def test_domain_allowlist(self):
        policy = NetworkPolicy(allowed_domains=["openai.com", "github.com"])
        guard = NetworkSecurityGuard(policy)
        assert guard.validate_url("https://openai.com").allowed is True
        assert guard.validate_url("https://evil.com").allowed is False

    def test_empty_domain(self):
        guard = NetworkSecurityGuard()
        verdict = guard.validate_url("")
        assert verdict.allowed is False

    def test_request_validation(self):
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        req = NetworkRequest(url="https://example.com", method="POST", body_size=1000)
        verdict = guard.validate_request(req)
        assert verdict.allowed is True

    def test_request_size_limit(self):
        policy = NetworkPolicy(max_request_size=100)
        guard = NetworkSecurityGuard(policy)
        req = NetworkRequest(url="https://example.com", body_size=200)
        verdict = guard.validate_request(req)
        assert verdict.allowed is False

    def test_sanitize_url(self):
        guard = NetworkSecurityGuard()
        clean = guard.sanitize_url("https://user:pass@example.com/path")
        assert "user" not in clean
        assert "pass" not in clean


class TestBrowserSecurity:
    def test_validate_navigation(self):
        guard = BrowserSecurityGuard(BrowserSandboxPolicy(
            allowed_origins=["example.com"],
        ))
        assert guard.validate_navigation("https://example.com").allowed is True
        assert guard.validate_navigation("https://evil.com").allowed is False

    def test_default_policy(self):
        guard = BrowserSecurityGuard()
        verdict = guard.validate_navigation("https://any.com")
        assert verdict.allowed is True


# ═══════════════════════════════════════════════════════════════════
# Phase 5.27: Execution Control
# ═══════════════════════════════════════════════════════════════════

class TestExecutionControl:
    def test_kill_switch(self):
        ec = ExecutionController()
        ec.kill()
        assert ec.state == ExecutionState.STOPPED
        assert ec.can_execute() is False

    def test_pause_resume(self):
        ec = ExecutionController()
        ec.pause()
        assert ec.state == ExecutionState.PAUSED
        ec.resume()
        assert ec.state == ExecutionState.RUNNING

    def test_rate_limiting(self):
        ec = ExecutionController(RateLimitConfig(max_per_minute=3))
        for _ in range(3):
            ec.record_execution()
        status = ec.get_rate_status()
        assert status["per_minute"] == 3

    def test_execution_gates(self):
        ec = ExecutionController()
        gate = ExecutionGate(
            name="test_gate",
            enabled=True,
            check_fn=lambda: False,
        )
        ec.add_gate(gate)
        assert ec.can_execute() is False

    def test_disabled_gate_passes(self):
        ec = ExecutionController()
        gate = ExecutionGate(
            name="test_gate",
            enabled=False,
            check_fn=lambda: False,
        )
        ec.add_gate(gate)
        assert ec.can_execute() is True

    def test_remove_gate(self):
        ec = ExecutionController()
        gate = ExecutionGate(name="g1", check_fn=lambda: False)
        ec.add_gate(gate)
        ec.remove_gate("g1")
        assert ec.can_execute() is True

    def test_state_listener(self):
        ec = ExecutionController()
        states = []
        ec.add_listener(lambda s: states.append(s))
        ec.kill()
        assert ExecutionState.STOPPED in states

    def test_reset(self):
        ec = ExecutionController()
        ec.kill()
        ec.reset()
        assert ec.state == ExecutionState.RUNNING

    def test_burst_limit(self):
        ec = ExecutionController(RateLimitConfig(burst_limit=5, max_per_minute=100))
        ec.record_execution()
        ec.record_execution()
        assert ec.can_execute() is True


# ═══════════════════════════════════════════════════════════════════
# Phase 5.28: Observability/Tracing
# ═══════════════════════════════════════════════════════════════════

class TestTracing:
    def test_trace_lifecycle(self):
        tc = TraceCollector()
        trace = tc.start_trace("t1", "goal1")
        assert trace.trace_id == "t1"
        span = tc.start_span("op1")
        assert span.name == "op1"
        tc.end_span()
        tc.end_trace()
        assert trace.end_time is not None

    def test_nested_spans(self):
        tc = TraceCollector()
        tc.start_trace("t1")
        outer = tc.start_span("outer")
        inner = tc.start_span("inner")
        tc.end_span()
        tc.end_span()
        tc.end_trace()
        assert inner.parent_id == outer.span_id

    def test_span_events(self):
        tc = TraceCollector()
        tc.start_trace("t1")
        span = tc.start_span("op")
        span.add_event("started", {"key": "value"})
        assert len(span.events) == 1
        tc.end_trace()

    def test_trace_summary(self):
        tc = TraceCollector()
        tc.start_trace("t1", "goal1")
        tc.start_span("op")
        tc.end_span(SpanStatus.OK.value)
        tc.end_trace()
        summary = tc.get_trace_summary("t1")
        assert summary["span_count"] == 1
        assert summary["status"] == "ok"

    def test_max_traces(self):
        tc = TraceCollector(max_traces=3)
        for i in range(5):
            tc.start_trace(f"t{i}")
            tc.end_trace()
        assert len(tc.get_all_traces()) == 3


class TestMetrics:
    def test_counter(self):
        mc = MetricsCollector()
        mc.increment("api_calls")
        mc.increment("api_calls", 5)
        assert mc.get_counter("api_calls") == 6

    def test_gauge(self):
        mc = MetricsCollector()
        mc.set_gauge("active_goals", 3.0)
        assert mc.get_gauge("active_goals") == 3.0

    def test_histogram(self):
        mc = MetricsCollector()
        mc.record_histogram("latency", 100.0)
        mc.record_histogram("latency", 200.0)
        stats = mc.get_histogram_stats("latency")
        assert stats["count"] == 2
        assert stats["avg"] == 150.0

    def test_all_metrics(self):
        mc = MetricsCollector()
        mc.increment("c1")
        mc.set_gauge("g1", 1.0)
        mc.record_histogram("h1", 50.0)
        all_m = mc.get_all_metrics()
        assert "counters" in all_m
        assert "gauges" in all_m
        assert "histograms" in all_m

    def test_reset(self):
        mc = MetricsCollector()
        mc.increment("c1")
        mc.reset()
        assert mc.get_counter("c1") == 0


# ═══════════════════════════════════════════════════════════════════
# Phase 5.29: Multi-Goal Management
# ═══════════════════════════════════════════════════════════════════

class TestMultiGoal:
    def test_add_and_get(self):
        mgm = MultiGoalManager()
        g = Goal(id="g1", description="Goal 1", status=GoalStatus.CREATED)
        mgm.add_goal(g)
        assert len(mgm.get_all_goals()) == 1

    def test_priority_scheduling(self):
        mgm = MultiGoalManager()
        g1 = Goal(id="g1", description="Low", status=GoalStatus.CREATED)
        g2 = Goal(id="g2", description="High", status=GoalStatus.CREATED)
        mgm.add_goal(g1, priority=GoalPriority.LOW.value)
        mgm.add_goal(g2, priority=GoalPriority.HIGH.value)
        next_goal = mgm.get_next_goal()
        assert next_goal.goal.id == "g2"

    def test_concurrent_limit(self):
        mgm = MultiGoalManager(max_concurrent=2)
        g1 = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        g2 = Goal(id="g2", description="G2", status=GoalStatus.CREATED)
        g3 = Goal(id="g3", description="G3", status=GoalStatus.CREATED)
        mgm.add_goal(g1)
        mgm.add_goal(g2)
        mgm.add_goal(g3)
        mgm.start_goal("g1")
        mgm.start_goal("g2")
        assert mgm.get_running_count() == 2
        assert mgm.get_next_goal() is None

    def test_dependency_resolution(self):
        mgm = MultiGoalManager(max_concurrent=5)
        g1 = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        g2 = Goal(id="g2", description="G2", status=GoalStatus.CREATED)
        mgm.add_goal(g1)
        mgm.add_goal(g2, depends_on=["g1"])
        mgm.start_goal("g1")
        mgm.complete_goal("g1", success=True)
        next_goal = mgm.get_next_goal()
        assert next_goal.goal.id == "g2"

    def test_completion_callback(self):
        mgm = MultiGoalManager()
        completed = []
        mgm.add_completion_callback(lambda s: completed.append(s.goal.id))
        g = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        mgm.add_goal(g)
        mgm.start_goal("g1")
        mgm.complete_goal("g1", success=True)
        assert "g1" in completed

    def test_pause_resume(self):
        mgm = MultiGoalManager()
        g = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        mgm.add_goal(g)
        mgm.start_goal("g1")
        mgm.pause_goal("g1")
        assert mgm.get_goals_by_status(GoalScheduleStatus.PAUSED.value)
        mgm.resume_goal("g1")
        assert mgm.get_goals_by_status(GoalScheduleStatus.RUNNING.value)

    def test_remove_goal(self):
        mgm = MultiGoalManager()
        g = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        mgm.add_goal(g)
        assert mgm.remove_goal("g1") is True
        assert len(mgm.get_all_goals()) == 0

    def test_summary(self):
        mgm = MultiGoalManager()
        g = Goal(id="g1", description="G1", status=GoalStatus.CREATED)
        mgm.add_goal(g)
        summary = mgm.get_summary()
        assert summary["total"] == 1


# ═══════════════════════════════════════════════════════════════════
# Phase 5.30: Integration Validation
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_validation(self):
        validator = IntegrationValidator()
        report = validator.run_all_checks()
        assert report.total > 0
        assert report.overall_passed is True
        assert report.failed == 0

    def test_all_checks_pass(self):
        validator = IntegrationValidator()
        report = validator.run_all_checks()
        for check in report.checks:
            assert check.passed, f"Check '{check.name}' failed: {check.message}"

    def test_report_serialization(self):
        validator = IntegrationValidator()
        report = validator.run_all_checks()
        d = report.to_dict()
        assert "total" in d
        assert "checks" in d
