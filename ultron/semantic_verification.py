"""Semantic Verification for JARVIS Phase 5.

Extends the existing VerificationEngine with LLM-powered semantic checks
that evaluate whether task outputs satisfy requirements.

Architecture:
    Task Objective + Success Criteria + Actual Result
        ↓
    Step 1: Evidence Extraction
        ↓
    Step 2: Per-Criterion Verification
        ↓
    Step 3: Cross-Task Consistency Check
        ↓
    Structured Verification Result
        ↓
    (deterministic checks remain as-is)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ultron.llm.base import LLMProvider, ProviderResult
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.verification_v5 import (
    TaskVerificationResult,
    VerificationCheck,
    VerificationCheckType,
    VerificationEngine,
)

logger = logging.getLogger("ultron.semantic_verification")


from ultron.semantic_verification_types import (
    EvidenceItem,
    SemanticCheckResult,
    SemanticVerificationResult,
)


@dataclass
class CrossTaskCheck:
    """Result of cross-task consistency verification."""
    task_a: str = ""
    task_b: str = ""
    consistent: bool = False
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_a": self.task_a,
            "task_b": self.task_b,
            "consistent": self.consistent,
            "reasoning": self.reasoning,
        }


@dataclass
class MultiStepVerificationResult:
    """Result of the full multi-step verification pipeline."""
    overall_passed: bool = False
    confidence: float = 0.0
    evidence: List[EvidenceItem] = field(default_factory=list)
    criteria_checks: List[SemanticCheckResult] = field(default_factory=list)
    cross_task_checks: List[CrossTaskCheck] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "criteria_checks": [c.to_dict() for c in self.criteria_checks],
            "cross_task_checks": [c.to_dict() for c in self.cross_task_checks],
            "summary": self.summary,
        }


class SemanticVerifier:
    """LLM-powered semantic verification of task outputs.

    Evaluates whether actual results satisfy the task's objectives
    and success criteria, going beyond structural checks.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        fallback: Optional[VerificationEngine] = None,
    ) -> None:
        self._provider = provider
        self._fallback = fallback or VerificationEngine()

    def verify(
        self,
        task_id: str,
        execution_result: ExecutionResult,
        objective: str = "",
        success_criteria: Optional[List[str]] = None,
        checks: Optional[List[VerificationCheck]] = None,
    ) -> TaskVerificationResult:
        """Verify a task result using semantic analysis.

        Falls back to deterministic checks if LLM is unavailable.
        """
        # Always run deterministic checks first
        if checks:
            det_result = self._fallback.verify_task(task_id, execution_result, checks)
        else:
            det_result = self._fallback.verify_simple(task_id, execution_result)

        # If deterministic checks failed hard, don't override with semantic
        if not det_result.overall_passed and det_result.confidence == 0.0:
            return det_result

        # Run semantic verification
        if self._provider and success_criteria:
            semantic = self._semantic_verify(
                task_id, execution_result, objective, success_criteria,
            )

            # Combine results: deterministic AND semantic must pass
            combined_passed = det_result.overall_passed and semantic.overall_passed
            combined_confidence = (det_result.confidence + semantic.confidence) / 2

            det_result.overall_passed = combined_passed
            det_result.confidence = combined_confidence

            # Add semantic check results as messages
            for check in semantic.checks:
                if not check.passed:
                    det_result.message += f" [SEMANTIC] {check.criterion}: {check.reasoning}"

        return det_result

    def verify_simple_semantic(
        self,
        task_id: str,
        execution_result: ExecutionResult,
        objective: str,
    ) -> SemanticVerificationResult:
        """Quick semantic verification without full check structure."""
        if not self._provider:
            return SemanticVerificationResult(
                overall_passed=execution_result.status == ExecutionStatus.SUCCESS,
                confidence=0.5,
                summary="No LLM provider available for semantic verification",
            )

        output_text = json.dumps(execution_result.output, default=str)[:2000]

        prompt = (
            f"Verify if this output satisfies the objective.\n\n"
            f"Objective: {objective}\n"
            f"Output: {output_text}\n"
            f"Status: {execution_result.status.value}\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"passed": true/false, "confidence": 0.0-1.0, "reasoning": "..."}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_semantic_result(result.text)
        except Exception as exc:
            logger.warning("Semantic verification failed: %s", exc)

        return SemanticVerificationResult(
            overall_passed=execution_result.status == ExecutionStatus.SUCCESS,
            confidence=0.3,
            summary="LLM semantic verification failed, using status-based fallback",
        )

    def _semantic_verify(
        self,
        task_id: str,
        execution_result: ExecutionResult,
        objective: str,
        criteria: List[str],
    ) -> SemanticVerificationResult:
        """Run LLM semantic verification against success criteria."""
        output_text = json.dumps(execution_result.output, default=str)[:2000]
        criteria_text = "; ".join(criteria)

        prompt = (
            f"Verify if this output satisfies the success criteria.\n\n"
            f"Task objective: {objective}\n"
            f"Success criteria: {criteria_text}\n"
            f"Output: {output_text}\n"
            f"Status: {execution_result.status.value}\n\n"
            "For each criterion, determine if it is satisfied.\n"
            "Respond with ONLY a JSON object:\n"
            '{"overall": true/false, "confidence": 0.0-1.0, "checks": [{"criterion": "...", "passed": true/false, "confidence": 0.0-1.0, "reasoning": "..."}], "summary": "..."}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_semantic_result(result.text, criteria)
        except Exception as exc:
            logger.warning("LLM semantic verification failed: %s", exc)

        return SemanticVerificationResult(
            overall_passed=execution_result.status == ExecutionStatus.SUCCESS,
            confidence=0.3,
            summary="LLM verification failed, falling back to status check",
        )

    # ── Multi-step Verification Pipeline ────────────────────────────

    def extract_evidence(
        self,
        execution_result: ExecutionResult,
        objective: str,
    ) -> List[EvidenceItem]:
        """Step 1: Extract evidence from task output.

        Uses the LLM to identify key pieces of evidence that support
        or contradict the task objective.
        """
        if not self._provider:
            # Fallback: treat entire output as evidence
            output_text = json.dumps(execution_result.output, default=str)[:2000]
            return [EvidenceItem(
                source="output",
                content=output_text,
                relevance=0.5,
            )]

        output_text = json.dumps(execution_result.output, default=str)[:3000]
        prompt = (
            f"Extract key evidence from this task output that supports or "
            f"contradicts the objective.\n\n"
            f"Objective: {objective}\n"
            f"Output: {output_text}\n\n"
            "Respond with ONLY a JSON array of evidence items:\n"
            '[{"source": "section_name", "content": "evidence text", "relevance": 0.0-1.0}, ...]\n'
            "Each item should be a distinct piece of evidence. Include 1-5 items."
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_evidence(result.text)
        except Exception as exc:
            logger.warning("Evidence extraction failed: %s", exc)

        # Fallback
        return [EvidenceItem(
            source="output",
            content=output_text[:500],
            relevance=0.5,
        )]

    def verify_criteria(
        self,
        evidence: List[EvidenceItem],
        criteria: List[str],
        objective: str,
    ) -> Tuple[List[SemanticCheckResult], float]:
        """Step 2: Verify each criterion against extracted evidence.

        Returns (checks, confidence).
        """
        if not self._provider:
            return (
                [SemanticCheckResult(criterion=c, passed=False, confidence=0.0,
                    reasoning="No LLM provider available") for c in criteria],
                0.0,
            )

        evidence_text = "\n".join(
            f"- [{e.source}] {e.content}" for e in evidence
        )
        criteria_text = "\n".join(f"- {c}" for c in criteria)

        prompt = (
            f"Verify each criterion against the extracted evidence.\n\n"
            f"Objective: {objective}\n"
            f"Evidence:\n{evidence_text}\n"
            f"Criteria:\n{criteria_text}\n\n"
            "For each criterion, determine if the evidence supports it.\n"
            "Respond with ONLY a JSON object:\n"
            '{"checks": [{"criterion": "...", "passed": true/false, "confidence": 0.0-1.0, "reasoning": "..."}], "overall_confidence": 0.0-1.0}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_criteria_checks(result.text, criteria)
        except Exception as exc:
            logger.warning("Criteria verification failed: %s", exc)

        return (
            [SemanticCheckResult(criterion=c, passed=False, confidence=0.3,
                reasoning="LLM verification failed") for c in criteria],
            0.3,
        )

    def cross_task_verify(
        self,
        results: List[Tuple[str, ExecutionResult]],
    ) -> List[CrossTaskCheck]:
        """Step 3: Cross-task consistency verification.

        Takes a list of (task_id, execution_result) pairs and checks
        whether their outputs are consistent with each other.
        """
        if len(results) < 2:
            return []

        if not self._provider:
            return [CrossTaskCheck(
                task_a=r[0], task_b=results[i+1][0],
                consistent=True, reasoning="No LLM provider available",
            ) for i, r in enumerate(results[:-1])]

        summaries = []
        for task_id, er in results:
            output_text = json.dumps(er.output, default=str)[:500]
            summaries.append(f"Task {task_id}: {er.status.value} — {output_text}")

        prompt = (
            "Check whether these task outputs are consistent with each other.\n\n"
            "Task outputs:\n" + "\n".join(summaries) + "\n\n"
            "For each pair of tasks, determine if their outputs conflict.\n"
            "Respond with ONLY a JSON object:\n"
            '{"checks": [{"task_a": "...", "task_b": "...", "consistent": true/false, "reasoning": "..."}]}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_cross_task_checks(result.text)
        except Exception as exc:
            logger.warning("Cross-task verification failed: %s", exc)

        return [CrossTaskCheck(
            task_a=results[i][0], task_b=results[i+1][0],
            consistent=True, reasoning="LLM verification failed",
        ) for i in range(len(results) - 1)]

    def verify_multi_step(
        self,
        task_id: str,
        execution_result: ExecutionResult,
        objective: str,
        criteria: List[str],
        prior_results: Optional[List[Tuple[str, ExecutionResult]]] = None,
    ) -> MultiStepVerificationResult:
        """Full multi-step verification pipeline.

        Steps:
        1. Extract evidence from output
        2. Verify each criterion against evidence
        3. Cross-task consistency check (if prior results provided)
        4. Combine results
        """
        # Step 1: Evidence extraction
        evidence = self.extract_evidence(execution_result, objective)

        # Step 2: Per-criterion verification
        criteria_checks, criteria_confidence = self.verify_criteria(
            evidence, criteria, objective,
        )

        # Step 3: Cross-task verification (optional)
        cross_task_checks: List[CrossTaskCheck] = []
        if prior_results and len(prior_results) >= 1:
            all_results = prior_results + [(task_id, execution_result)]
            cross_task_checks = self.cross_task_verify(all_results)

        # Step 4: Combine results
        all_passed = all(c.passed for c in criteria_checks) if criteria_checks else False
        cross_consistent = all(c.consistent for c in cross_task_checks) if cross_task_checks else True

        overall_passed = all_passed and cross_consistent

        # Confidence: average of criteria confidence, penalized by cross-task conflicts
        if criteria_checks:
            avg_confidence = sum(c.confidence for c in criteria_checks) / len(criteria_checks)
        else:
            avg_confidence = 0.5

        if cross_task_checks and not cross_consistent:
            avg_confidence *= 0.7  # Penalty for cross-task conflicts

        summary_parts = []
        passed_count = sum(1 for c in criteria_checks if c.passed)
        summary_parts.append(f"{passed_count}/{len(criteria_checks)} criteria passed")
        if cross_task_checks:
            consistent_count = sum(1 for c in cross_task_checks if c.consistent)
            summary_parts.append(f"{consistent_count}/{len(cross_task_checks)} cross-task checks consistent")

        return MultiStepVerificationResult(
            overall_passed=overall_passed,
            confidence=avg_confidence,
            evidence=evidence,
            criteria_checks=criteria_checks,
            cross_task_checks=cross_task_checks,
            summary="; ".join(summary_parts),
        )

    # ── Evidence Parsing ────────────────────────────────────────────

    def _parse_evidence(self, text: str) -> List[EvidenceItem]:
        """Parse LLM evidence extraction response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                items = []
                for item in data:
                    if isinstance(item, dict):
                        items.append(EvidenceItem(
                            source=str(item.get("source", "")),
                            content=str(item.get("content", "")),
                            relevance=float(item.get("relevance", 0.5)),
                        ))
                return items if items else [EvidenceItem(source="output", content=cleaned[:500], relevance=0.5)]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return [EvidenceItem(source="output", content=cleaned[:500], relevance=0.5)]

    def _parse_criteria_checks(
        self, text: str, expected_criteria: List[str],
    ) -> Tuple[List[SemanticCheckResult], float]:
        """Parse LLM criteria verification response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                checks = []
                for c in data.get("checks", []):
                    if isinstance(c, dict):
                        checks.append(SemanticCheckResult(
                            criterion=str(c.get("criterion", "")),
                            passed=bool(c.get("passed", False)),
                            confidence=float(c.get("confidence", 0.5)),
                            reasoning=str(c.get("reasoning", "")),
                        ))
                overall_confidence = float(data.get("overall_confidence", 0.5))
                return checks, overall_confidence
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return (
            [SemanticCheckResult(criterion=c, passed=False, confidence=0.2,
                reasoning="Failed to parse LLM response") for c in expected_criteria],
            0.2,
        )

    def _parse_cross_task_checks(self, text: str) -> List[CrossTaskCheck]:
        """Parse LLM cross-task verification response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                checks = []
                for c in data.get("checks", []):
                    if isinstance(c, dict):
                        checks.append(CrossTaskCheck(
                            task_a=str(c.get("task_a", "")),
                            task_b=str(c.get("task_b", "")),
                            consistent=bool(c.get("consistent", True)),
                            reasoning=str(c.get("reasoning", "")),
                        ))
                return checks
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return []

    def _parse_semantic_result(
        self,
        text: str,
        expected_criteria: Optional[List[str]] = None,
    ) -> SemanticVerificationResult:
        """Parse LLM semantic verification response."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                checks = []
                for c in data.get("checks", []):
                    if isinstance(c, dict):
                        checks.append(SemanticCheckResult(
                            criterion=str(c.get("criterion", "")),
                            passed=bool(c.get("passed", False)),
                            confidence=float(c.get("confidence", 0.5)),
                            reasoning=str(c.get("reasoning", "")),
                        ))

                return SemanticVerificationResult(
                    overall_passed=bool(data.get("overall", data.get("passed", False))),
                    confidence=float(data.get("confidence", 0.5)),
                    checks=checks,
                    summary=str(data.get("summary", "")),
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return SemanticVerificationResult(
            overall_passed=False,
            confidence=0.2,
            summary="Failed to parse LLM verification response",
        )


__all__ = [
    "SemanticCheckResult",
    "SemanticVerificationResult",
    "SemanticVerifier",
    "EvidenceItem",
    "CrossTaskCheck",
    "MultiStepVerificationResult",
]
