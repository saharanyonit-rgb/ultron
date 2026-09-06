"""Tests for enhanced Semantic Verification (multi-step pipeline, evidence, cross-task)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from ultron.llm.base import ProviderResult
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.semantic_verification import (
    CrossTaskCheck,
    EvidenceItem,
    MultiStepVerificationResult,
    SemanticCheckResult,
    SemanticVerifier,
)


def _mock_provider(text: str) -> MagicMock:
    provider = MagicMock()
    provider.complete.return_value = ProviderResult(text=text, tool_calls=[])
    provider.name = "mock"
    return provider


def _mock_result(output: dict | None = None) -> ExecutionResult:
    return ExecutionResult(
        tool_name="test",
        status=ExecutionStatus.SUCCESS,
        output=output or {"result": "success"},
    )


def _evidence_json() -> str:
    return json.dumps([
        {"source": "output_line_1", "content": "File created successfully", "relevance": 0.9},
        {"source": "output_line_2", "content": "Path: /tmp/test.txt", "relevance": 0.7},
    ])


def _criteria_json() -> str:
    return json.dumps({
        "checks": [
            {"criterion": "File exists", "passed": True, "confidence": 0.95, "reasoning": "Output confirms creation"},
            {"criterion": "Content non-empty", "passed": True, "confidence": 0.8, "reasoning": "No empty warnings"},
        ],
        "overall_confidence": 0.87,
    })


def _cross_task_json() -> str:
    return json.dumps({
        "checks": [
            {"task_a": "t1", "task_b": "t2", "consistent": True, "reasoning": "Outputs are compatible"},
        ]
    })


# ═══════════════════════════════════════════════════════════════════
# Evidence Extraction
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceExtraction:
    def test_extracts_evidence_with_llm(self):
        provider = _mock_provider(_evidence_json())
        verifier = SemanticVerifier(provider=provider)
        result = _mock_result()

        evidence = verifier.extract_evidence(result, "Create a file")

        assert len(evidence) == 2
        assert evidence[0].source == "output_line_1"
        assert evidence[0].relevance == 0.9
        provider.complete.assert_called_once()

    def test_fallback_without_provider(self):
        verifier = SemanticVerifier(provider=None)
        result = _mock_result({"key": "value"})

        evidence = verifier.extract_evidence(result, "Objective")

        assert len(evidence) == 1
        assert evidence[0].source == "output"
        assert evidence[0].relevance == 0.5

    def test_fallback_on_llm_error(self):
        provider = MagicMock()
        provider.complete.side_effect = Exception("LLM error")
        verifier = SemanticVerifier(provider=provider)
        result = _mock_result()

        evidence = verifier.extract_evidence(result, "Objective")

        assert len(evidence) == 1
        assert evidence[0].source == "output"


# ═══════════════════════════════════════════════════════════════════
# Criteria Verification
# ═══════════════════════════════════════════════════════════════════

class TestCriteriaVerification:
    def test_verifies_criteria_with_evidence(self):
        provider = _mock_provider(_criteria_json())
        verifier = SemanticVerifier(provider=provider)

        evidence = [
            EvidenceItem(source="out", content="File created", relevance=0.9),
        ]

        checks, confidence = verifier.verify_criteria(
            evidence, ["File exists", "Content non-empty"], "Create file",
        )

        assert len(checks) == 2
        assert checks[0].passed is True
        assert checks[1].passed is True
        assert confidence == 0.87

    def test_fallback_without_provider(self):
        verifier = SemanticVerifier(provider=None)

        checks, confidence = verifier.verify_criteria(
            [], ["criterion"], "Objective",
        )

        assert len(checks) == 1
        assert checks[0].passed is False
        assert confidence == 0.0


# ═══════════════════════════════════════════════════════════════════
# Cross-Task Verification
# ═══════════════════════════════════════════════════════════════════

class TestCrossTaskVerification:
    def test_checks_consistency_between_tasks(self):
        provider = _mock_provider(_cross_task_json())
        verifier = SemanticVerifier(provider=provider)

        results = [
            ("t1", _mock_result({"file": "a.txt"})),
            ("t2", _mock_result({"file": "b.txt"})),
        ]

        checks = verifier.cross_task_verify(results)

        assert len(checks) == 1
        assert checks[0].consistent is True
        assert checks[0].task_a == "t1"
        assert checks[0].task_b == "t2"

    def test_no_pairs_for_single_task(self):
        verifier = SemanticVerifier(provider=MagicMock())
        checks = verifier.cross_task_verify([("t1", _mock_result())])
        assert checks == []

    def test_no_pairs_for_empty(self):
        verifier = SemanticVerifier(provider=MagicMock())
        checks = verifier.cross_task_verify([])
        assert checks == []

    def test_fallback_without_provider(self):
        verifier = SemanticVerifier(provider=None)

        results = [
            ("t1", _mock_result()),
            ("t2", _mock_result()),
        ]

        checks = verifier.cross_task_verify(results)

        assert len(checks) == 1
        assert checks[0].consistent is True


# ═══════════════════════════════════════════════════════════════════
# Multi-Step Pipeline
# ═══════════════════════════════════════════════════════════════════

class TestMultiStepPipeline:
    def test_full_pipeline(self):
        provider = _mock_provider_sequence([
            _evidence_json(),       # extract_evidence
            _criteria_json(),       # verify_criteria
        ])
        verifier = SemanticVerifier(provider=provider)
        result = _mock_result()

        mr = verifier.verify_multi_step(
            task_id="t1",
            execution_result=result,
            objective="Create a file",
            criteria=["File exists", "Content non-empty"],
        )

        assert isinstance(mr, MultiStepVerificationResult)
        assert mr.overall_passed is True
        assert mr.confidence > 0.8
        assert len(mr.evidence) == 2
        assert len(mr.criteria_checks) == 2
        assert "2/2 criteria passed" in mr.summary

    def test_pipeline_with_cross_task(self):
        provider = _mock_provider_sequence([
            _evidence_json(),       # extract_evidence
            _criteria_json(),       # verify_criteria
            _cross_task_json(),     # cross_task_verify
        ])
        verifier = SemanticVerifier(provider=provider)

        prior = [("t0", _mock_result({"step": "done"}))]
        mr = verifier.verify_multi_step(
            task_id="t1",
            execution_result=_mock_result(),
            objective="Multi-step task",
            criteria=["criterion"],
            prior_results=prior,
        )

        assert mr.overall_passed is True
        assert len(mr.cross_task_checks) == 1
        assert "cross-task checks consistent" in mr.summary

    def test_pipeline_without_provider(self):
        verifier = SemanticVerifier(provider=None)
        result = _mock_result()

        mr = verifier.verify_multi_step(
            task_id="t1",
            execution_result=result,
            objective="Objective",
            criteria=["criterion"],
        )

        assert mr.overall_passed is False
        assert mr.confidence == 0.0

    def test_cross_task_conflict_reduces_confidence(self):
        """When cross-task checks fail, overall confidence is penalized."""
        cross_conflict = json.dumps({
            "checks": [
                {"task_a": "t0", "task_b": "t1", "consistent": False, "reasoning": "Contradictory outputs"},
            ]
        })

        provider = _mock_provider_sequence([
            _evidence_json(),       # extract_evidence
            _criteria_json(),       # verify_criteria
            cross_conflict,         # cross_task_verify
        ])
        verifier = SemanticVerifier(provider=provider)

        prior = [("t0", _mock_result({"status": "done"}))]
        mr = verifier.verify_multi_step(
            task_id="t1",
            execution_result=_mock_result(),
            objective="Task",
            criteria=["c1", "c2"],
            prior_results=prior,
        )

        # Confidence should be penalized (0.87 * 0.7 ≈ 0.609)
        assert mr.confidence < 0.7
        assert mr.cross_task_checks[0].consistent is False


# ═══════════════════════════════════════════════════════════════════
# Data Class Serialization
# ═══════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_evidence_to_dict(self):
        e = EvidenceItem(source="src", content="text", relevance=0.8)
        d = e.to_dict()
        assert d["source"] == "src"
        assert d["relevance"] == 0.8

    def test_cross_task_check_to_dict(self):
        c = CrossTaskCheck(task_a="t1", task_b="t2", consistent=True, reasoning="ok")
        d = c.to_dict()
        assert d["consistent"] is True

    def test_multi_step_result_to_dict(self):
        mr = MultiStepVerificationResult(
            overall_passed=True,
            confidence=0.9,
            evidence=[EvidenceItem(source="s", content="c", relevance=0.8)],
            criteria_checks=[SemanticCheckResult(criterion="c", passed=True, confidence=0.9, reasoning="r")],
            cross_task_checks=[CrossTaskCheck(task_a="a", task_b="b", consistent=True, reasoning="r")],
            summary="All passed",
        )
        d = mr.to_dict()
        assert d["overall_passed"] is True
        assert len(d["evidence"]) == 1
        assert len(d["criteria_checks"]) == 1
        assert len(d["cross_task_checks"]) == 1


def _mock_provider_sequence(texts: list[str]) -> MagicMock:
    provider = MagicMock()
    provider.complete.side_effect = [
        ProviderResult(text=t, tool_calls=[]) for t in texts
    ]
    provider.name = "mock"
    return provider
