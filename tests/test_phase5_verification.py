"""Tests for Phase 5.7: Verification Engine."""

from __future__ import annotations

from ultron.models import ExecutionResult, ExecutionStatus
from ultron.verification_v5 import (
    TaskVerificationResult,
    VerificationCheck,
    VerificationCheckType,
    VerificationEngine,
)


class TestVerificationEngine:
    def test_verify_simple_success(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"data": "value"},
        )
        verification = engine.verify_simple("t1", result)
        assert verification.overall_passed
        assert verification.confidence == 1.0

    def test_verify_simple_failure(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.FAILED,
            error="something broke",
        )
        verification = engine.verify_simple("t1", result)
        assert not verification.overall_passed
        assert verification.confidence == 0.0

    def test_verify_status_check(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={},
        )
        checks = [VerificationCheck(
            check_type=VerificationCheckType.STATUS,
            description="check status",
        )]
        verification = engine.verify_task("t1", result, checks)
        assert verification.overall_passed
        assert verification.passed_count == 1

    def test_verify_output_keys(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"name": "test", "value": 42},
        )
        checks = [VerificationCheck(
            check_type=VerificationCheckType.OUTPUT_KEYS,
            description="check keys",
            expected_value=["name", "value"],
        )]
        verification = engine.verify_task("t1", result, checks)
        assert verification.overall_passed

    def test_verify_output_keys_missing(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"name": "test"},
        )
        checks = [VerificationCheck(
            check_type=VerificationCheckType.OUTPUT_KEYS,
            description="check keys",
            expected_value=["name", "missing_key"],
        )]
        verification = engine.verify_task("t1", result, checks)
        assert not verification.overall_passed

    def test_verify_content_contains(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"text": "hello world"},
        )
        checks = [VerificationCheck(
            check_type=VerificationCheckType.CONTENT_CONTAINS,
            description="check content",
            expected_value="hello",
        )]
        verification = engine.verify_task("t1", result, checks)
        assert verification.overall_passed

    def test_verify_no_checks(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={},
        )
        verification = engine.verify_task("t1", result, [])
        assert verification.overall_passed

    def test_verify_mixed_results(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"key": "value"},
        )
        checks = [
            VerificationCheck(
                check_type=VerificationCheckType.STATUS,
                description="status check",
            ),
            VerificationCheck(
                check_type=VerificationCheckType.OUTPUT_KEYS,
                description="key check",
                expected_value=["missing"],
            ),
        ]
        verification = engine.verify_task("t1", result, checks)
        assert not verification.overall_passed
        assert verification.passed_count == 1
        assert verification.failed_count == 1

    def test_build_checks_from_criteria(self):
        engine = VerificationEngine()
        criteria = [
            "File exists: test.txt",
            "Verification completed",
            "Output contains expected data",
        ]
        checks = engine.build_checks_from_criteria(criteria)
        assert len(checks) == 3
        assert checks[0].check_type == VerificationCheckType.FILE_EXISTS

    def test_custom_checker(self):
        engine = VerificationEngine()

        def my_checker(result: ExecutionResult, check: VerificationCheck) -> bool:
            return result.output.get("custom") == "ok"

        engine.register_checker("custom", my_checker)
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"custom": "ok"},
        )
        checks = [VerificationCheck(
            check_type=VerificationCheckType.CUSTOM,
            description="custom check",
            parameters={"checker_name": "custom"},
        )]
        verification = engine.verify_task("t1", result, checks)
        assert verification.overall_passed

    def test_verification_result_serialization(self):
        engine = VerificationEngine()
        result = ExecutionResult(
            tool_name="test",
            status=ExecutionStatus.SUCCESS,
            output={"key": "val"},
        )
        checks = [
            VerificationCheck(
                check_type=VerificationCheckType.STATUS,
                description="status",
            ),
        ]
        verification = engine.verify_task("t1", result, checks)
        d = verification.to_dict()
        assert d["task_id"] == "t1"
        assert d["overall_passed"]
        assert len(d["checks"]) == 1
