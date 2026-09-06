"""Verification Engine for JARVIS Phase 5: Autonomous Intelligence.

Provides structured verification of task execution results beyond simple
success/failure. Supports multiple verification strategies:
- Structural verification (output keys, types)
- File existence verification
- Content verification (expected content present)
- Custom criteria verification
- Semantic verification (keyword-based)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ultron.models import ExecutionResult, ExecutionStatus, VerificationResult, VerificationStatus

logger = logging.getLogger("ultron.verification_v5")


class VerificationCheckType(str, Enum):
    STATUS = "status"
    OUTPUT_KEYS = "output_keys"
    FILE_EXISTS = "file_exists"
    FILE_CONTENT = "file_content"
    CONTENT_CONTAINS = "content_contains"
    CUSTOM = "custom"


@dataclass
class VerificationCheck:
    """A single verification check to run against a task result."""

    check_type: VerificationCheckType
    description: str = ""
    expected_value: Any = None
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_type": self.check_type.value,
            "description": self.description,
            "expected_value": self.expected_value,
            "parameters": self.parameters,
        }


@dataclass
class VerificationCheckResult:
    """Result of a single verification check."""

    check: VerificationCheck
    passed: bool = False
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskVerificationResult:
    """Complete verification result for a task."""

    task_id: str = ""
    overall_passed: bool = False
    confidence: float = 0.0
    check_results: List[VerificationCheckResult] = field(default_factory=list)
    message: str = ""

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.check_results if r.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.check_results if not r.passed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "overall_passed": self.overall_passed,
            "confidence": self.confidence,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "message": self.message,
            "checks": [
                {
                    "description": r.check.description,
                    "type": r.check.check_type.value,
                    "passed": r.passed,
                    "message": r.message,
                }
                for r in self.check_results
            ],
        }


class VerificationEngine:
    """Structured verification engine for task execution results.

    Runs multiple verification checks and produces a structured result
    with confidence scoring.
    """

    def __init__(self) -> None:
        self._custom_checkers: Dict[str, Callable[..., bool]] = {}

    def register_checker(self, name: str, checker: Callable[..., bool]) -> None:
        """Register a custom verification checker."""
        self._custom_checkers[name] = checker

    def verify_task(
        self,
        task_id: str,
        execution_result: ExecutionResult,
        checks: List[VerificationCheck],
    ) -> TaskVerificationResult:
        """Run all verification checks against a task's execution result."""
        result = TaskVerificationResult(task_id=task_id)

        if not checks:
            result.overall_passed = execution_result.status == ExecutionStatus.SUCCESS
            result.confidence = 1.0 if result.overall_passed else 0.0
            result.message = "No verification checks specified" if not checks else "Execution status check only"
            return result

        for check in checks:
            check_result = self._run_check(check, execution_result)
            result.check_results.append(check_result)

        passed = sum(1 for r in result.check_results if r.passed)
        total = len(result.check_results)

        result.overall_passed = passed == total
        result.confidence = passed / total if total > 0 else 0.0

        if result.overall_passed:
            result.message = f"All {total} verification checks passed"
        else:
            failed = [r.check.description or r.check.check_type.value for r in result.check_results if not r.passed]
            result.message = f"Failed checks: {', '.join(failed)}"

        logger.info(
            "Verification [task_id=%s, passed=%d/%d, confidence=%.2f]",
            task_id,
            passed,
            total,
            result.confidence,
        )

        return result

    def verify_simple(
        self,
        task_id: str,
        execution_result: ExecutionResult,
    ) -> TaskVerificationResult:
        """Quick verification using only execution status."""
        result = TaskVerificationResult(task_id=task_id)
        result.overall_passed = execution_result.status == ExecutionStatus.SUCCESS
        result.confidence = 1.0 if result.overall_passed else 0.0
        result.message = "Execution succeeded" if result.overall_passed else f"Execution failed: {execution_result.error}"
        return result

    def _run_check(
        self,
        check: VerificationCheck,
        execution_result: ExecutionResult,
    ) -> VerificationCheckResult:
        """Run a single verification check."""
        result = VerificationCheckResult(check=check)

        try:
            if check.check_type == VerificationCheckType.STATUS:
                result.passed = execution_result.status == ExecutionStatus.SUCCESS
                result.message = f"Status: {execution_result.status.value}"

            elif check.check_type == VerificationCheckType.OUTPUT_KEYS:
                expected_keys = check.expected_value or []
                if isinstance(expected_keys, str):
                    expected_keys = [expected_keys]
                output_keys = set(execution_result.output.keys())
                missing = set(expected_keys) - output_keys
                result.passed = len(missing) == 0
                result.message = f"Missing keys: {missing}" if missing else "All keys present"
                result.details = {"output_keys": list(output_keys), "missing": list(missing)}

            elif check.check_type == VerificationCheckType.FILE_EXISTS:
                file_path = check.expected_value or check.parameters.get("path")
                if file_path:
                    path = Path(file_path)
                    result.passed = path.exists()
                    result.message = f"File {'exists' if result.passed else 'not found'}: {file_path}"
                else:
                    result.passed = False
                    result.message = "No file path specified"

            elif check.check_type == VerificationCheckType.FILE_CONTENT:
                file_path = check.parameters.get("path", check.expected_value)
                expected_content = check.parameters.get("content", "")
                if file_path:
                    path = Path(file_path)
                    if path.exists():
                        actual = path.read_text(encoding="utf-8")
                        result.passed = expected_content in actual
                        result.message = (
                            "Content matches" if result.passed
                            else f"Expected '{expected_content}' not found in file"
                        )
                    else:
                        result.passed = False
                        result.message = f"File not found: {file_path}"
                else:
                    result.passed = False
                    result.message = "No file path specified"

            elif check.check_type == VerificationCheckType.CONTENT_CONTAINS:
                expected = check.expected_value or ""
                if isinstance(expected, str):
                    expected = [expected]
                output_text = str(execution_result.output)
                found = [e for e in expected if e in output_text]
                result.passed = len(found) == len(expected)
                result.message = f"Found {len(found)}/{len(expected)} expected items"

            elif check.check_type == VerificationCheckType.CUSTOM:
                checker_name = check.parameters.get("checker_name", "")
                checker = self._custom_checkers.get(checker_name)
                if checker:
                    result.passed = checker(execution_result, check)
                    result.message = f"Custom check '{checker_name}' {'passed' if result.passed else 'failed'}"
                else:
                    result.passed = False
                    result.message = f"Custom checker '{checker_name}' not found"

            else:
                result.passed = False
                result.message = f"Unknown check type: {check.check_type}"

        except Exception as exc:
            result.passed = False
            result.message = f"Check error: {exc}"
            result.details = {"exception": str(exc)}

        return result

    def build_checks_from_criteria(self, criteria_descriptions: List[str]) -> List[VerificationCheck]:
        """Convert goal success criteria descriptions into verification checks."""
        checks = []

        for desc in criteria_descriptions:
            lower = desc.lower()

            if "file" in lower and ("exist" in lower or "created" in lower):
                path = desc.split(":")[-1].strip() if ":" in desc else ""
                checks.append(VerificationCheck(
                    check_type=VerificationCheckType.FILE_EXISTS,
                    description=desc,
                    expected_value=path,
                ))
            elif "file" in lower and ("content" in lower or "contain" in lower):
                checks.append(VerificationCheck(
                    check_type=VerificationCheckType.CUSTOM,
                    description=desc,
                    parameters={"checker_name": "file_content"},
                ))
            elif "verify" in lower or "check" in lower or "confirm" in lower:
                checks.append(VerificationCheck(
                    check_type=VerificationCheckType.STATUS,
                    description=desc,
                ))
            else:
                checks.append(VerificationCheck(
                    check_type=VerificationCheckType.OUTPUT_KEYS,
                    description=desc,
                    expected_value=[],
                ))

        return checks


__all__ = [
    "VerificationCheckType",
    "VerificationCheck",
    "VerificationCheckResult",
    "TaskVerificationResult",
    "VerificationEngine",
]
