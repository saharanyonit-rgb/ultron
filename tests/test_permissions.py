"""Tests for permissioned tool execution (ultron.actions.permissions)."""

from __future__ import annotations

from typing import Any

from ultron.actions import PermissionDecision, PermissionGate
from ultron.actions.permissions import CLIPermissionGate, SecurePermissionGate
from ultron.tools.base import Tool


class ReadOnlyTool(Tool):
    name = "read_only"
    description = "A read-only tool"
    parameters = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {}}
    mutates = False

    def run(self, **kwargs):
        return {"result": "ok"}


class MutatingTool(Tool):
    name = "mutating"
    description = "A mutating tool"
    parameters = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {}}
    mutates = True

    def run(self, **kwargs):
        return {"result": "done"}


def test_read_only_tool_passes_through():
    gate = SecurePermissionGate(confirm=lambda name, args: False)
    tool = ReadOnlyTool()
    decision = gate.check(tool, {})
    assert decision.allowed is True
    assert "read-only" in decision.reason


def test_mutating_tool_denied_by_default():
    gate = SecurePermissionGate()  # default: deny all
    tool = MutatingTool()
    decision = gate.check(tool, {})
    assert decision.allowed is False
    assert "denied" in decision.reason.lower()


def test_mutating_tool_allowed_by_callback():
    gate = SecurePermissionGate(confirm=lambda name, args: True)
    tool = MutatingTool()
    decision = gate.check(tool, {"key": "value"})
    assert decision.allowed is True
    assert "confirmed" in decision.reason.lower()


def test_confirmation_receives_arguments():
    received = {}

    def capture(name, args):
        received["name"] = name
        received["args"] = args
        return True

    gate = SecurePermissionGate(confirm=capture)
    tool = MutatingTool()
    gate.check(tool, {"path": "/tmp/test"})
    assert received["name"] == "mutating"
    assert received["args"]["path"] == "/tmp/test"


def test_confirmation_exception_denied():
    def boom(name, args):
        raise RuntimeError("callback crash")

    gate = SecurePermissionGate(confirm=boom)
    tool = MutatingTool()
    decision = gate.check(tool, {})
    assert decision.allowed is False
    assert "RuntimeError" in decision.reason


def test_cli_gate_is_secure_subclass():
    assert issubclass(CLIPermissionGate, SecurePermissionGate)


def test_base_permission_gate_unchanged():
    """Phase 1 PermissionGate still works as before."""
    gate = PermissionGate()
    tool = MutatingTool()
    decision = gate.check(tool, {})
    assert decision.allowed is True
    assert "pass-through" in decision.reason


def test_secure_gate_extends_permission_gate():
    gate = SecurePermissionGate()
    assert isinstance(gate, PermissionGate)
