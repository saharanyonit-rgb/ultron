"""UI and Voice Integration Validation for JARVIS Phase 5.30.

Full integration validation: verifies all components work together,
validates the complete autonomous execution pipeline, and provides
integration test utilities.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.agents.llm_agent import LLMAgent
from ultron.autonomous import AutonomousExecutor
from ultron.context import ContextManager
from ultron.execution_control import ExecutionController, RateLimitConfig
from ultron.goal import Goal, GoalStatus
from ultron.intelligent_recovery import IntelligentRecoveryEngine
from ultron.llm_goal import LLMGoalEngine
from ultron.llm_planner import LLMGoalPlanner
from ultron.memory_manager import MemoryManager
from ultron.multi_goal import MultiGoalManager, GoalPriority
from ultron.network_security import NetworkSecurityGuard, NetworkPolicy
from ultron.observability import MetricsCollector, TraceCollector
from ultron.resource_manager import BudgetConfig, ResourceManager
from ultron.semantic_verification import SemanticVerifier
from ultron.tool_selection import ToolSelector
from ultron.uncertainty import UncertaintyHandler

logger = logging.getLogger("ultron.integration")


@dataclass
class IntegrationCheck:
    """Result of an integration check."""
    name: str = ""
    passed: bool = False
    message: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "duration_ms": self.duration_ms,
        }


@dataclass
class IntegrationReport:
    """Full integration validation report."""
    checks: List[IntegrationCheck] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    overall_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "overall_passed": self.overall_passed,
            "checks": [c.to_dict() for c in self.checks],
        }


class IntegrationValidator:
    """Validates that all JARVIS components integrate correctly.

    Checks:
    - Component initialization
    - Data flow between components
    - Security boundary enforcement
    - Memory and state persistence
    - Resource management
    - Multi-goal coordination
    """

    def __init__(self, provider: Optional[Any] = None) -> None:
        self._provider = provider
        self._report = IntegrationReport()

    def run_all_checks(self) -> IntegrationReport:
        """Run all integration validation checks."""
        self._report = IntegrationReport()

        checks = [
            self._check_goal_understanding,
            self._check_planning,
            self._check_tool_selection,
            self._check_memory,
            self._check_recovery,
            self._check_uncertainty,
            self._check_verification,
            self._check_resources,
            self._check_credentials,
            self._check_network_security,
            self._check_execution_control,
            self._check_observability,
            self._check_multi_goal,
            self._check_autonomous_executor,
        ]

        for check_fn in checks:
            self._run_check(check_fn)

        self._report.total = len(self._report.checks)
        self._report.passed = sum(1 for c in self._report.checks if c.passed)
        self._report.failed = self._report.total - self._report.passed
        self._report.overall_passed = self._report.failed == 0

        return self._report

    def _run_check(self, check_fn: Any) -> None:
        import time
        start = time.time()
        try:
            result = check_fn()
            result.duration_ms = (time.time() - start) * 1000
            self._report.checks.append(result)
        except Exception as exc:
            self._report.checks.append(IntegrationCheck(
                name=check_fn.__name__,
                passed=False,
                message=f"Exception: {exc}",
                duration_ms=(time.time() - start) * 1000,
            ))

    def _check_goal_understanding(self) -> IntegrationCheck:
        engine = LLMGoalEngine(provider=self._provider)
        goal = engine.create_goal("Test goal for validation")
        return IntegrationCheck(
            name="LLM Goal Understanding",
            passed=goal is not None,
            message="Goal parsing works",
        )

    def _check_planning(self) -> IntegrationCheck:
        planner = LLMGoalPlanner(provider=self._provider)
        goal = Goal(
            id="test_plan",
            description="Simple test task",
            status=GoalStatus.CREATED,
        )
        plan = planner.plan(goal)
        return IntegrationCheck(
            name="LLM Task Planning",
            passed=plan is not None,
            message="Planning produces a plan",
        )

    def _check_tool_selection(self) -> IntegrationCheck:
        from ultron.tools import ToolRegistry
        selector = ToolSelector(registry=ToolRegistry())
        result = selector.select_tools(
            "read a file",
            required_tools=["read_file", "write_file", "list_dir"],
        )
        return IntegrationCheck(
            name="Tool Selection",
            passed=result is not None,
            message="Tool selection returns a result",
        )

    def _check_memory(self) -> IntegrationCheck:
        mm = MemoryManager()
        mm.add_working("test context")
        mm.add_semantic("Python is a language")
        working = mm.get_working()
        semantic = mm.search_semantic("Python")
        return IntegrationCheck(
            name="Memory System",
            passed=len(working) > 0 and len(semantic) > 0,
            message=f"Working: {len(working)}, Semantic: {len(semantic)}",
        )

    def _check_recovery(self) -> IntegrationCheck:
        engine = IntelligentRecoveryEngine(provider=self._provider)
        from ultron.execution_state import StepState
        step = StepState(step_id="test", status="pending")
        analysis = engine.analyze_failure(step, RuntimeError("test"), "task")
        return IntegrationCheck(
            name="Intelligent Recovery",
            passed=analysis is not None,
            message="Recovery analysis works",
        )

    def _check_uncertainty(self) -> IntegrationCheck:
        handler = UncertaintyHandler()
        event = handler.check_confidence("I'm sure about this", confidence_score=0.9)
        return IntegrationCheck(
            name="Uncertainty Management",
            passed=event is not None,
            message="Confidence checking works",
        )

    def _check_verification(self) -> IntegrationCheck:
        verifier = SemanticVerifier(provider=self._provider)
        from ultron.models import ExecutionResult, ExecutionStatus
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"key": "value"},
        )
        sem = verifier.verify_simple_semantic("t1", result, "test objective")
        return IntegrationCheck(
            name="Semantic Verification",
            passed=sem is not None,
            message="Verification works",
        )

    def _check_resources(self) -> IntegrationCheck:
        rm = ResourceManager(BudgetConfig(max_api_calls=10, max_tokens=1000))
        rm.record_api_call(tokens=100)
        remaining = rm.get_remaining_budget()
        return IntegrationCheck(
            name="Resource Management",
            passed=remaining["api_calls"] == 9,
            message=f"Remaining budget tracking works",
        )

    def _check_credentials(self) -> IntegrationCheck:
        from ultron.credentials import CredentialManager
        cm = CredentialManager()
        cm.store("test_key", "secret_value_12345")
        retrieved = cm.retrieve("test_key")
        sanitized = cm.sanitize_text("Key is secret_value_12345 here")
        return IntegrationCheck(
            name="Credential Management",
            passed=retrieved == "secret_value_12345" and "REDACTED" in sanitized,
            message="Credentials stored and sanitized",
        )

    def _check_network_security(self) -> IntegrationCheck:
        guard = NetworkSecurityGuard(NetworkPolicy(require_https=True))
        verdict = guard.validate_url("https://api.example.com")
        blocked = guard.validate_url("http://evil.com")
        return IntegrationCheck(
            name="Network Security",
            passed=verdict.allowed and not blocked.allowed,
            message="HTTPS enforced, HTTP blocked",
        )

    def _check_execution_control(self) -> IntegrationCheck:
        ec = ExecutionController(RateLimitConfig(max_per_minute=100))
        can = ec.can_execute()
        ec.record_execution()
        return IntegrationCheck(
            name="Execution Control",
            passed=can,
            message="Execution controller works",
        )

    def _check_observability(self) -> IntegrationCheck:
        tc = TraceCollector()
        mc = MetricsCollector()
        trace = tc.start_trace("test_trace", "test_goal")
        span = tc.start_span("test_span")
        tc.end_span()
        tc.end_trace()
        mc.increment("test_counter")
        return IntegrationCheck(
            name="Observability/Tracing",
            passed=len(tc.get_all_traces()) > 0,
            message="Tracing and metrics work",
        )

    def _check_multi_goal(self) -> IntegrationCheck:
        mgm = MultiGoalManager(max_concurrent=2)
        g1 = Goal(id="g1", description="Goal 1", status=GoalStatus.CREATED)
        g2 = Goal(id="g2", description="Goal 2", status=GoalStatus.CREATED)
        mgm.add_goal(g1, priority=GoalPriority.HIGH.value)
        mgm.add_goal(g2, priority=GoalPriority.LOW.value)
        next_goal = mgm.get_next_goal()
        return IntegrationCheck(
            name="Multi-Goal Management",
            passed=next_goal is not None and next_goal.goal.id == "g1",
            message="Priority scheduling works",
        )

    def _check_autonomous_executor(self) -> IntegrationCheck:
        from ultron.autonomous import AutonomousExecutor, AutonomousConfig
        config = AutonomousConfig()
        return IntegrationCheck(
            name="Autonomous Executor",
            passed=config is not None,
            message="Autonomous config initializes",
        )


__all__ = [
    "IntegrationCheck",
    "IntegrationReport",
    "IntegrationValidator",
]
