"""Tests for risk classification and permission policy (Phase 4)."""

from __future__ import annotations

from ultron.risk import RiskLevel, RiskClassifier, DEFAULT_RISK_MAP
from ultron.policy import PolicyAction, PolicyDecision, PolicyEngine, DEFAULT_POLICY


def test_risk_classifier_read():
    classifier = RiskClassifier()
    assert classifier.classify("get_system_info") == RiskLevel.READ
    assert classifier.classify("read_file") == RiskLevel.READ
    assert classifier.classify("search_files") == RiskLevel.READ


def test_risk_classifier_low():
    classifier = RiskClassifier()
    assert classifier.classify("set_clipboard") == RiskLevel.LOW
    assert classifier.classify("open_app") == RiskLevel.LOW


def test_risk_classifier_medium():
    classifier = RiskClassifier()
    assert classifier.classify("create_file") == RiskLevel.MEDIUM
    assert classifier.classify("close_app") == RiskLevel.MEDIUM


def test_risk_classifier_high():
    classifier = RiskClassifier()
    assert classifier.classify("delete_file") == RiskLevel.HIGH
    assert classifier.classify("rename_file") == RiskLevel.HIGH


def test_risk_classifier_critical():
    classifier = RiskClassifier()
    assert classifier.classify("execute_command") == RiskLevel.CRITICAL
    assert classifier.classify("execute_shell") == RiskLevel.CRITICAL


def test_risk_classifier_unknown_tool():
    classifier = RiskClassifier()
    assert classifier.classify("unknown_tool") == RiskLevel.MEDIUM


def test_risk_classifier_custom_registration():
    classifier = RiskClassifier()
    classifier.register("custom_tool", RiskLevel.LOW)
    assert classifier.classify("custom_tool") == RiskLevel.LOW


def test_policy_engine_allow():
    engine = PolicyEngine()
    decision = engine.evaluate("get_system_info", RiskLevel.READ)
    assert decision.action == PolicyAction.ALLOW


def test_policy_engine_confirm():
    engine = PolicyEngine()
    decision = engine.evaluate("create_file", RiskLevel.MEDIUM)
    assert decision.action == PolicyAction.CONFIRM


def test_policy_engine_deny():
    engine = PolicyEngine()
    decision = engine.evaluate("execute_command", RiskLevel.CRITICAL)
    assert decision.action == PolicyAction.DENY


def test_policy_engine_tool_override():
    engine = PolicyEngine()
    engine.set_tool_override("custom_tool", PolicyAction.ALLOW)
    decision = engine.evaluate("custom_tool", RiskLevel.CRITICAL)
    assert decision.action == PolicyAction.ALLOW


def test_policy_engine_confirm_callback_true():
    engine = PolicyEngine(confirm_callback=lambda t, a, r: True)
    allowed = engine.request_permission("create_file", RiskLevel.MEDIUM)
    assert allowed is True


def test_policy_engine_confirm_callback_false():
    engine = PolicyEngine(confirm_callback=lambda t, a, r: False)
    allowed = engine.request_permission("create_file", RiskLevel.MEDIUM)
    assert allowed is False


def test_policy_engine_no_callback_denies():
    engine = PolicyEngine()
    allowed = engine.request_permission("create_file", RiskLevel.MEDIUM)
    assert allowed is False


def test_policy_engine_set_policy():
    engine = PolicyEngine()
    engine.set_policy(RiskLevel.CRITICAL, PolicyAction.CONFIRM)
    policy = engine.get_policy()
    assert policy[RiskLevel.CRITICAL] == PolicyAction.CONFIRM


def test_default_risk_map_keys():
    assert "get_system_info" in DEFAULT_RISK_MAP
    assert "read_file" in DEFAULT_RISK_MAP
    assert "delete_file" in DEFAULT_RISK_MAP
    assert "execute_command" in DEFAULT_RISK_MAP


def test_default_policy_keys():
    assert RiskLevel.READ in DEFAULT_POLICY
    assert RiskLevel.CRITICAL in DEFAULT_POLICY
