"""Verification layer for JARVIS tool execution results.

JARVIS must not blindly trust tool execution.  The Verifier checks:
  1. Was the operation actually executed?
  2. Did the tool return successfully (no error key)?
  3. Is the result structurally valid (expected keys present)?
  4. Does the result satisfy the requested operation?

Phase 1 verification is simple and reliable — not autonomous AI evaluation.
Phase 3 adds SemanticVerifier for keyword-based semantic checks.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ultron.models import (
    ExecutionResult,
    ExecutionStatus,
    VerificationResult,
    VerificationStatus,
)

logger = logging.getLogger("ultron.verification")


class Verifier:
    """Verifies tool execution results for structural and semantic correctness."""

    def verify(
        self,
        execution_result: ExecutionResult,
        expected_output_keys: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Run all verification checks against an execution result.

        Returns a VerificationResult with per-check outcomes.
        """
        checks: Dict[str, bool] = {}

        # Check 1: Was the operation executed at all?
        checks["executed"] = execution_result.status != ExecutionStatus.NOT_FOUND

        # Check 2: Did the tool report success?
        checks["no_error"] = (
            execution_result.error is None
            and execution_result.status == ExecutionStatus.SUCCESS
        )

        # Check 3: Is the result structurally valid?
        checks["valid_structure"] = self._check_structure(
            execution_result, expected_output_keys
        )

        # Check 4: Does the result satisfy the request?
        checks["satisfies_request"] = self._check_satisfaction(execution_result)

        # Overall verdict
        all_passed = all(checks.values())
        status = VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        message = self._build_message(checks, status)

        logger.info(
            "Verification: tool=%s status=%s checks=%s",
            execution_result.tool_name,
            status.value,
            checks,
        )

        return VerificationResult(
            execution_result=execution_result,
            status=status,
            checks=checks,
            message=message,
        )

    def _check_structure(
        self,
        result: ExecutionResult,
        expected_keys: Optional[List[str]] = None,
    ) -> bool:
        """Verify the output dict has expected keys (if specified)."""
        if not expected_keys:
            return True
        return all(key in result.output for key in expected_keys)

    def _check_satisfaction(self, result: ExecutionResult) -> bool:
        """Check that the result logically satisfies the requested operation.

        Phase 1: basic checks only — success status and no error field.
        """
        if result.status in (ExecutionStatus.NOT_FOUND, ExecutionStatus.UNAVAILABLE):
            return False
        if "error" in result.output:
            return False
        return True

    def _build_message(self, checks: Dict[str, bool], status: VerificationStatus) -> str:
        failed = [k for k, v in checks.items() if not v]
        if status == VerificationStatus.PASSED:
            return "All verification checks passed."
        return f"Verification failed: {', '.join(failed)}"


class SemanticVerifier:
    """Verifies if execution results semantically satisfy objectives.

    Uses keyword matching and structural analysis (no LLM calls for V1).
    """

    def __init__(self) -> None:
        self._structural_verifier = Verifier()

    def verify(
        self,
        execution_result: ExecutionResult,
        objective: str,
        expected_keywords: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Verify if the result satisfies the given objective."""
        structural = self._structural_verifier.verify(execution_result)

        checks = dict(structural.checks)

        if expected_keywords:
            output_text = str(execution_result.output).lower()
            keyword_hits = sum(1 for kw in expected_keywords if kw.lower() in output_text)
            checks["semantic_keywords"] = keyword_hits > 0
        else:
            checks["semantic_keywords"] = True

        output = execution_result.output
        checks["has_meaningful_output"] = bool(output) and not all(
            k == "error" for k in output.keys()
        )

        all_passed = all(checks.values())
        status = VerificationStatus.PASSED if all_passed else VerificationStatus.FAILED
        failed = [k for k, v in checks.items() if not v]
        message = "All checks passed" if all_passed else f"Failed: {', '.join(failed)}"

        return VerificationResult(
            execution_result=execution_result,
            status=status,
            checks=checks,
            message=message,
        )


__all__ = ["Verifier", "SemanticVerifier"]
