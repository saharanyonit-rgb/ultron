"""Tests for Phases 5.19-5.21: LLM Recovery, Uncertainty, Semantic Verification."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.execution_state import StepState
from ultron.intelligent_recovery import IntelligentRecoveryEngine, RecoveryAnalysis
from ultron.llm.base import ProviderResult
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.recovery import RecoveryAction
from ultron.semantic_verification import (
    SemanticCheckResult,
    SemanticVerifier,
    SemanticVerificationResult,
)
from ultron.uncertainty import ConfidenceLevel, UncertaintyEvent, UncertaintyHandler
from ultron.verification_v5 import (
    VerificationCheck,
    VerificationCheckType,
    VerificationEngine,
)


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


def _step(retry_count: int = 0) -> StepState:
    return StepState(step_id="s1", status="pending", retry_count=retry_count)


# ═══════════════════════════════════════════════════════════════════
# Phase 5.19: LLM Recovery
# ═══════════════════════════════════════════════════════════════════

class TestIntelligentRecoveryAnalysis:
    def test_llm_analysis(self):
        """LLM analyzes failure and suggests recovery."""
        analysis_json = json.dumps({
            "error_summary": "File not found",
            "likely_cause": "Wrong path",
            "suggested_action": "change_approach",
            "confidence": 0.8,
            "reasoning": "File path seems incorrect",
        })
        provider = _mock_provider(analysis_json)
        engine = IntelligentRecoveryEngine(provider=provider)

        step = _step()
        analysis = engine.analyze_failure(step, FileNotFoundError("/bad/path"), "Read config")

        assert analysis.likely_cause == "Wrong path"
        assert analysis.confidence == 0.8
        assert analysis.suggested_action == "change_approach"

    def test_fallback_analysis(self):
        """Falls back to heuristic when LLM unavailable."""
        engine = IntelligentRecoveryEngine(provider=None)
        step = _step()
        analysis = engine.analyze_failure(step, RuntimeError("fail"), "task")

        assert analysis.confidence == 0.3
        assert "heuristic" in analysis.reasoning.lower()

    def test_llm_error_falls_back(self):
        """LLM error triggers fallback analysis."""
        provider = _mock_provider_error()
        engine = IntelligentRecoveryEngine(provider=provider)
        step = _step()
        analysis = engine.analyze_failure(step, RuntimeError("fail"), "task")

        assert analysis.confidence == 0.3


class TestIntelligentRecoveryDecision:
    def test_high_confidence_uses_llm_action(self):
        """High confidence LLM suggestion overrides heuristic."""
        analysis_json = json.dumps({
            "error_summary": "timeout",
            "likely_cause": "network issue",
            "suggested_action": "retry",
            "confidence": 0.9,
            "reasoning": "Transient error",
        })
        provider = _mock_provider(analysis_json)
        engine = IntelligentRecoveryEngine(provider=provider, max_retries=3)

        step = _step(retry_count=0)
        decision = engine.decide_recovery_intelligent(
            step, TimeoutError("timeout"), "Fetch data",
        )

        assert decision.action == RecoveryAction.RETRY
        assert "LLM" in decision.reason

    def test_low_confidence_uses_heuristic(self):
        """Low confidence falls back to heuristic decision."""
        analysis_json = json.dumps({
            "error_summary": "error",
            "likely_cause": "unknown",
            "suggested_action": "abort",
            "confidence": 0.2,
            "reasoning": "not sure",
        })
        provider = _mock_provider(analysis_json)
        engine = IntelligentRecoveryEngine(provider=provider, max_retries=3)

        step = _step(retry_count=0)
        decision = engine.decide_recovery_intelligent(
            step, RuntimeError("fail"), "task",
        )

        # Low confidence means heuristic decision is used
        assert decision.action in (RecoveryAction.RETRY, RecoveryAction.ABORT, RecoveryAction.SKIP)

    def test_retry_limit_respected(self):
        """Retry limits are still respected regardless of LLM suggestion."""
        analysis_json = json.dumps({
            "error_summary": "error",
            "likely_cause": "unknown",
            "suggested_action": "retry",
            "confidence": 0.9,
            "reasoning": "try again",
        })
        provider = _mock_provider(analysis_json)
        engine = IntelligentRecoveryEngine(provider=provider, max_retries=2)

        step = _step(retry_count=2)  # Already at limit
        decision = engine.decide_recovery_intelligent(
            step, RuntimeError("fail"), "task",
        )

        assert decision.action == RecoveryAction.ABORT


class TestRecoveryAnalysisSerialization:
    def test_to_dict(self):
        analysis = RecoveryAnalysis(
            error_summary="test error",
            likely_cause="test cause",
            suggested_action="retry",
            confidence=0.7,
            reasoning="because",
        )
        d = analysis.to_dict()
        assert d["error_summary"] == "test error"
        assert d["confidence"] == 0.7


# ═══════════════════════════════════════════════════════════════════
# Phase 5.20: Uncertainty Management
# ═══════════════════════════════════════════════════════════════════

class TestConfidenceCheck:
    def test_high_confidence(self):
        """Confident text gets high confidence."""
        handler = UncertaintyHandler()
        event = handler.check_confidence("The answer is definitely 42.")

        assert event.confidence_level == ConfidenceLevel.HIGH.value
        assert event.confidence_score >= 0.7

    def test_hedging_detected(self):
        """Hedging language reduces confidence."""
        handler = UncertaintyHandler()
        event = handler.check_confidence(
            "It might be possible that this could be the answer, but I'm not sure."
        )

        assert event.confidence_level in (
            ConfidenceLevel.MEDIUM.value,
            ConfidenceLevel.LOW.value,
        )
        assert len(event.context["hedging_phrases"]) > 0

    def test_explicit_confidence(self):
        """Explicit confidence score is respected."""
        handler = UncertaintyHandler()
        event = handler.check_confidence("result", confidence_score=0.3)

        assert event.confidence_level == ConfidenceLevel.LOW.value
        assert event.confidence_score == 0.3

    def test_escalation_on_low_confidence(self):
        """Low confidence triggers escalation when enabled."""
        handler = UncertaintyHandler(require_action_on_low_confidence=True)
        event = handler.check_confidence(
            "I'm not sure about this result",
            confidence_score=0.2,
        )

        assert event.requires_action is True

    def test_no_escalation_by_default(self):
        """By default, no escalation is required."""
        handler = UncertaintyHandler()
        event = handler.check_confidence(
            "I'm not sure",
            confidence_score=0.1,
        )

        assert event.requires_action is False


class TestAmbiguityCheck:
    def test_relevant_response(self):
        """Response matching topic gets high confidence."""
        handler = UncertaintyHandler()
        event = handler.check_ambiguity(
            "Python is a programming language",
            expected_topic="Python programming",
        )

        assert event.confidence_score > 0.5

    def test_irrelevant_response(self):
        """Off-topic response gets low confidence."""
        handler = UncertaintyHandler()
        event = handler.check_ambiguity(
            "The weather is nice today",
            expected_topic="Python programming language",
        )

        assert event.confidence_score < 0.5


class TestConflictCheck:
    def test_no_conflicts(self):
        """Consistent results have no conflicts."""
        handler = UncertaintyHandler()
        event = handler.check_conflicting_results([
            {"result": True},
            {"result": True},
        ])

        assert event.confidence_level == ConfidenceLevel.HIGH.value

    def test_conflicts_detected(self):
        """Conflicting results are detected."""
        handler = UncertaintyHandler()
        event = handler.check_conflicting_results([
            {"result": True},
            {"result": False},
        ])

        assert event.confidence_level == ConfidenceLevel.LOW.value
        assert event.requires_action is True

    def test_single_result_no_conflict(self):
        """Single result has no conflicts."""
        handler = UncertaintyHandler()
        event = handler.check_conflicting_results([{"result": True}])

        assert event.confidence_level == ConfidenceLevel.HIGH.value


class TestUncertaintySummary:
    def test_summary(self):
        handler = UncertaintyHandler(require_action_on_low_confidence=True)
        handler.check_confidence("sure thing", confidence_score=0.9)
        handler.check_confidence("not sure", confidence_score=0.2)
        handler.check_confidence("maybe", confidence_score=0.5)

        summary = handler.get_summary()
        assert summary["total_events"] == 3
        assert summary["requires_action"] >= 1


# ═══════════════════════════════════════════════════════════════════
# Phase 5.21: Semantic Verification
# ═══════════════════════════════════════════════════════════════════

class TestSemanticVerification:
    def test_llm_verification_passed(self):
        """LLM confirms output satisfies criteria."""
        verify_json = json.dumps({
            "overall": True,
            "confidence": 0.9,
            "checks": [
                {"criterion": "File exists", "passed": True, "confidence": 0.95, "reasoning": "File created"},
            ],
            "summary": "All criteria met",
        })
        provider = _mock_provider(verify_json)
        verifier = SemanticVerifier(provider=provider)

        result = ExecutionResult(
            tool_name="create_file",
            status=ExecutionStatus.SUCCESS,
            output={"created": True, "path": "test.txt"},
        )

        sem_result = verifier.verify_simple_semantic(
            "t1", result, "Create a test file",
        )

        assert sem_result.overall_passed is True
        assert sem_result.confidence == 0.9

    def test_llm_verification_failed(self):
        """LLM rejects output as insufficient."""
        verify_json = json.dumps({
            "overall": False,
            "confidence": 0.8,
            "checks": [],
            "summary": "File was not actually created",
        })
        provider = _mock_provider(verify_json)
        verifier = SemanticVerifier(provider=provider)

        result = ExecutionResult(
            tool_name="create_file",
            status=ExecutionStatus.SUCCESS,
            output={"error": "permission denied"},
        )

        sem_result = verifier.verify_simple_semantic(
            "t1", result, "Create a test file",
        )

        assert sem_result.overall_passed is False

    def test_fallback_without_provider(self):
        """Without LLM, uses status-based verification."""
        verifier = SemanticVerifier(provider=None)
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"key": "value"},
        )

        sem_result = verifier.verify_simple_semantic("t1", result, "do something")

        assert sem_result.overall_passed is True
        assert sem_result.confidence == 0.5

    def test_full_verify_combines_results(self):
        """Full verify combines deterministic and semantic results."""
        verify_json = json.dumps({
            "overall": True,
            "confidence": 0.9,
            "checks": [],
            "summary": "Passed",
        })
        provider = _mock_provider(verify_json)
        verifier = SemanticVerifier(provider=provider)

        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"result": "data"},
        )

        checks = [
            VerificationCheck(
                check_type=VerificationCheckType.STATUS,
                description="Check status",
            ),
        ]

        final = verifier.verify("t1", result, "objective", ["criteria met"], checks)

        assert final.overall_passed is True
        assert final.confidence > 0

    def test_deterministic_failure_not_overridden(self):
        """Hard deterministic failure is not overridden by semantic pass."""
        verify_json = json.dumps({
            "overall": True,
            "confidence": 0.9,
            "checks": [],
            "summary": "Looks good",
        })
        provider = _mock_provider(verify_json)
        verifier = SemanticVerifier(provider=provider)

        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.FAILED,
            output={"error": "failed"},
        )

        checks = [
            VerificationCheck(
                check_type=VerificationCheckType.STATUS,
                description="Check status",
            ),
        ]

        final = verifier.verify("t1", result, "objective", ["criteria"], checks)

        # Deterministic check failed (status != SUCCESS), so overall should fail
        assert final.overall_passed is False


class TestSemanticCheckResult:
    def test_serialization(self):
        check = SemanticCheckResult(
            criterion="File created",
            passed=True,
            confidence=0.9,
            reasoning="File exists",
        )
        d = check.to_dict()
        assert d["criterion"] == "File created"
        assert d["passed"] is True
