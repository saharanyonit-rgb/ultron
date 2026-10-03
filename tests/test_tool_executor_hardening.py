"""Tests that tool execution cannot bypass the permission gate or audit log.

The specialized brains (coding/computer/research) and the autonomous executor
share a single `ToolExecutor`. When it was constructed bare it defaulted to a
pass-through `PermissionGate` and `audit_log=None`, so every goal-mode request
from the dashboard executed tools with no confirmation and no audit trail even
when `ULTRON_REQUIRE_PERMISSION=true`. These tests pin that shut.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ultron.actions import PermissionDecision, PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.risk import RiskLevel
from ultron.tools import ToolExecutor, ToolRegistry
from ultron.tools.base import Tool


class _MutatingTool(Tool):
    name = "audit_probe_mutate"
    description = "Test tool that reports whether it ran."
    parameters = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {"ran": {"type": "boolean"}}}
    risk = RiskLevel.HIGH
    mutates = True

    def __init__(self) -> None:
        self.ran = False

    def run(self, **kwargs):
        self.ran = True
        return {"ran": True}


class _DenyEverythingGate(PermissionGate):
    def check(self, tool, arguments) -> PermissionDecision:  # type: ignore[override]
        return PermissionDecision(allowed=False, reason="denied by test gate")


def _executor(gate, tmp_path) -> tuple[ToolExecutor, AuditLog]:
    audit = AuditLog(tmp_path / "audit.log")
    tool = _MutatingTool()
    return ToolExecutor(ToolRegistry([tool]), gate=gate, audit_log=audit), audit


def test_denied_tool_does_not_run(tmp_path):
    tool = _MutatingTool()
    registry = ToolRegistry([tool])
    audit = AuditLog(tmp_path / "audit.log")
    executor = ToolExecutor(registry, gate=_DenyEverythingGate(), audit_log=audit)

    result = executor.execute("audit_probe_mutate", {})

    assert tool.ran is False
    assert result.allowed is False
    assert result.status.value == "permission_denied"


def test_denial_is_audit_logged(tmp_path):
    tool = _MutatingTool()
    registry = ToolRegistry([tool])
    audit = AuditLog(tmp_path / "audit.log")
    executor = ToolExecutor(registry, gate=_DenyEverythingGate(), audit_log=audit)

    executor.execute("audit_probe_mutate", {"x": 1})

    events = audit.entries()
    assert events, "a denied call must still leave an audit record"


def test_successful_call_is_audit_logged(tmp_path):
    tool = _MutatingTool()
    registry = ToolRegistry([tool])
    audit = AuditLog(tmp_path / "audit.log")
    executor = ToolExecutor(registry, gate=PermissionGate(), audit_log=audit)

    result = executor.execute("audit_probe_mutate", {})

    assert result.allowed is True
    events = audit.entries()
    assert events, "an executed call must leave an audit record"


_ENTRYPOINTS = ("ultron/cli.py", "desktop/server.py")


@pytest.mark.parametrize("rel_path", _ENTRYPOINTS)
def test_entrypoints_do_not_build_a_bare_executor(rel_path):
    """A `ToolExecutor(registry)` with no gate/audit is the bypass being fixed.

    Checked statically so the guarantee does not depend on importing and
    starting a web server.
    """
    source = open(Path(__file__).resolve().parents[1] / rel_path, encoding="utf-8").read()
    tree = ast.parse(source)

    bare: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "ToolExecutor"):
            continue
        supplied = {kw.arg for kw in node.keywords if kw.arg}
        positional = len(node.args)
        # registry is positional; a bare call supplies nothing else.
        if positional <= 1 and not {"gate", "audit_log"} & supplied:
            bare.append(node.lineno)

    assert not bare, (
        f"{rel_path} constructs a ToolExecutor without a gate or audit log at "
        f"line(s) {bare}; that bypasses permission checks and audit logging"
    )
