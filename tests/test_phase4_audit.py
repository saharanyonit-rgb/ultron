"""Tests for audit event system (Phase 4)."""

from __future__ import annotations

import json

from ultron.audit import AuditEvent, AuditLogger, EventType, SENSITIVE_KEYS


def test_audit_event_creation():
    event = AuditEvent(event_type=EventType.REQUEST_RECEIVED, request_id="r1")
    assert event.event_type == EventType.REQUEST_RECEIVED
    assert event.request_id == "r1"


def test_audit_event_to_dict():
    event = AuditEvent(
        event_type=EventType.TOOL_EXECUTED,
        tool_name="read_file",
        success=True,
        metadata={"duration_ms": 10.5},
    )
    d = event.to_dict()
    assert d["event_type"] == "tool_executed"
    assert d["tool_name"] == "read_file"
    assert d["success"] is True


def test_audit_event_redacts_sensitive():
    event = AuditEvent(
        event_type=EventType.TOOL_REQUESTED,
        metadata={"api_key": "secret123", "normal_key": "value"},
    )
    d = event.to_dict()
    assert d["metadata"]["api_key"] == "***REDACTED***"
    assert d["metadata"]["normal_key"] == "value"


def test_audit_logger_log():
    logger = AuditLogger()
    event = AuditEvent(event_type=EventType.REQUEST_RECEIVED, request_id="r1")
    logger.log(event)
    assert len(logger.events) == 1
    assert logger.events[0].request_id == "r1"


def test_audit_logger_log_request_received():
    logger = AuditLogger()
    logger.log_request_received("r1", "hello world")
    assert len(logger.events) == 1
    assert logger.events[0].event_type == EventType.REQUEST_RECEIVED


def test_audit_logger_log_tool_executed():
    logger = AuditLogger()
    logger.log_tool_executed("r1", "read_file", True, 10.5)
    assert len(logger.events) == 1
    assert logger.events[0].tool_name == "read_file"


def test_audit_logger_log_permission():
    logger = AuditLogger()
    logger.log_permission_decision("r1", "create_file", True, "medium")
    assert len(logger.events) == 1
    assert logger.events[0].success is True


def test_audit_logger_log_verification():
    logger = AuditLogger()
    logger.log_verification("r1", "tool", True, {"check": True})
    assert len(logger.events) == 1


def test_audit_logger_log_retry():
    logger = AuditLogger()
    logger.log_retry("r1", "s1", 1, "timeout")
    assert len(logger.events) == 1
    assert logger.events[0].metadata["retry_count"] == 1


def test_audit_logger_get_trace():
    logger = AuditLogger()
    logger.log_request_received("r1", "input")
    logger.log_tool_executed("r1", "tool", True, 10)
    logger.log_request_received("r2", "other")

    trace = logger.get_trace("r1")
    assert len(trace) == 2


def test_audit_logger_persistence(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    logger = AuditLogger(log_path)
    logger.log_request_received("r1", "hello")

    with log_path.open("r") as f:
        lines = f.readlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["event_type"] == "request_received"


def test_audit_logger_clear():
    logger = AuditLogger()
    logger.log_request_received("r1", "hello")
    logger.clear()
    assert len(logger.events) == 0


def test_sensitive_keys():
    assert "api_key" in SENSITIVE_KEYS
    assert "password" in SENSITIVE_KEYS
    assert "token" in SENSITIVE_KEYS


def test_event_type_values():
    assert EventType.REQUEST_RECEIVED.value == "request_received"
    assert EventType.TOOL_EXECUTED.value == "tool_executed"
    assert EventType.FINAL_RESPONSE.value == "final_response"
