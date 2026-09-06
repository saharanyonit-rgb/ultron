"""Unit tests for Tool Registry & Safe Tool Execution (`ultron.tools`)."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from ultron.actions import PermissionDecision, PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.core.brain import Brain, ResponseStatus, UserRequest
from ultron.core.router import IntentRouter, RouteType
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.memory import Memory
from ultron.tools import (
    ALL_TOOLS,
    InvalidParametersError,
    InvalidToolError,
    Tool,
    ToolAlreadyExistsError,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolExecutor,
    ToolNotFoundError,
    ToolRegistry,
    ToolSpec,
)


class DummyTool(Tool):
    name = "dummy_tool"
    description = "A dummy tool for unit testing."
    parameters = {
        "type": "object",
        "properties": {
            "val": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["val"],
    }
    output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}

    def __init__(self, should_raise: bool = False) -> None:
        self.should_raise = should_raise

    def run(self, val: str, count: int = 1, **kwargs: Any) -> Dict[str, Any]:
        if self.should_raise:
            raise RuntimeError("Dummy tool internal crash")
        return {"result": val * count}


class DenyingGate(PermissionGate):
    def check(self, tool: Tool, arguments: dict[str, Any]) -> PermissionDecision:
        return PermissionDecision(allowed=False, reason="Denied for security testing")


class ScriptedProvider(LLMProvider):
    name = "scripted_tool_provider"

    def complete(self, text, tools):
        return ProviderResult(text="scripted response", tool_calls=[])

    def feed_tool_results(self, results):
        pass


# --- Test 1 — Register tool ---
def test_register_valid_tool():
    registry = ToolRegistry([])
    dummy = DummyTool()
    registry.register(dummy)

    assert registry.exists("dummy_tool")
    assert registry.get("dummy_tool") is dummy


# --- Test 2 — Duplicate registration ---
def test_duplicate_registration_rejected():
    registry = ToolRegistry([])
    dummy1 = DummyTool()
    dummy2 = DummyTool()

    registry.register(dummy1)
    with pytest.raises(ToolAlreadyExistsError, match="already registered"):
        registry.register(dummy2)

    # Overwrite allowed if explicit
    registry.register(dummy2, allow_overwrite=True)
    assert registry.get("dummy_tool") is dummy2


# --- Test 3 — Lookup ---
def test_tool_lookup_and_metadata():
    registry = ToolRegistry(ALL_TOOLS)

    assert registry.exists("get_system_info")
    tool = registry.get("get_system_info")
    assert tool is not None
    assert tool.name == "get_system_info"
    assert len(registry.all()) >= 10
    assert len(registry.specs()) >= 10


# --- Test 4 — Missing tool ---
def test_missing_tool_execution_handled(tmp_path):
    registry = ToolRegistry([])
    executor = ToolExecutor(registry=registry)

    result = executor.execute("non_existent_tool", {})
    assert result.status == ToolExecutionStatus.FAILURE
    assert result.allowed is False
    assert "unknown tool" in result.output["error"].lower()


# --- Test 5 — Parameter validation ---
def test_parameter_validation():
    tool = DummyTool()

    # Missing required parameter 'val'
    valid, err = tool.validate_parameters({})
    assert valid is False
    assert "Missing required parameter" in err

    # Wrong type for 'count' (expected int, got string)
    valid, err = tool.validate_parameters({"val": "hello", "count": "not_an_int"})
    assert valid is False
    assert "must be of type integer" in err

    # Correct parameters
    valid, err = tool.validate_parameters({"val": "hello", "count": 2})
    assert valid is True
    assert err is None


# --- Test 6 — Successful execution ---
def test_successful_tool_execution(tmp_path):
    registry = ToolRegistry([])
    dummy = DummyTool()
    registry.register(dummy)
    audit = AuditLog(tmp_path / "audit.log")
    executor = ToolExecutor(registry=registry, audit_log=audit)

    res: ToolExecutionResult = executor.execute("dummy_tool", {"val": "hi", "count": 3})

    assert res.status == ToolExecutionStatus.SUCCESS
    assert res.allowed is True
    assert res.output == {"result": "hihihi"}
    assert res.error is None
    assert len(audit.entries()) == 1


# --- Test 7 — Tool failure ---
def test_tool_exception_handled(tmp_path):
    registry = ToolRegistry([])
    failing_tool = DummyTool(should_raise=True)
    registry.register(failing_tool)
    executor = ToolExecutor(registry=registry)

    res = executor.execute("dummy_tool", {"val": "boom"})

    assert res.status == ToolExecutionStatus.FAILURE
    assert "RuntimeError" in res.output["error"]
    assert res.error is not None


# --- Test 8 — Permission denial ---
def test_permission_denial(tmp_path):
    registry = ToolRegistry([])
    dummy = DummyTool()
    registry.register(dummy)
    executor = ToolExecutor(registry=registry, gate=DenyingGate())

    res = executor.execute("dummy_tool", {"val": "secure"})

    assert res.status == ToolExecutionStatus.PERMISSION_DENIED
    assert res.allowed is False
    assert "Denied for security" in res.output["error"]


# --- Test 9 — Execution isolation ---
def test_execution_isolation():
    registry = ToolRegistry([DummyTool()])
    executor = ToolExecutor(registry=registry)

    # Initial state
    initial_specs = [s.name for s in registry.specs()]

    executor.execute("dummy_tool", {"val": "test"})

    # Registry state must remain untouched
    assert [s.name for s in registry.specs()] == initial_specs


# --- Test 10 — Brain integration ---
def test_brain_integration_with_tools(tmp_path):
    provider = ScriptedProvider()
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
    )
    brain = Brain(agent=agent)

    # Route: TOOL (get_system_info)
    resp = brain.process("get system info")

    assert resp.status == ResponseStatus.SUCCESS
    assert resp.metadata.get("route") == "tool"


# --- Test 11 — Router integration ---
def test_router_integration_with_registry():
    registry = ToolRegistry(ALL_TOOLS)
    router = IntentRouter(tools=registry.all())

    decision = router.route("take a screenshot")
    assert decision.route_type == RouteType.TOOL
    assert decision.target == "take_screenshot"
    assert registry.exists(decision.target)
