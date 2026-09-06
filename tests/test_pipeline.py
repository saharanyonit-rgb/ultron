"""Tests for the pipeline layer (ultron.pipeline)."""

from __future__ import annotations

from typing import List, Optional

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.core.router import IntentRouter, RouteType
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.memory import Memory
from ultron.models import RuntimeContext, VerificationStatus
from ultron.pipeline import Pipeline, PipelineResult
from ultron.tools import ALL_TOOLS, ToolRegistry


class ScriptedProvider(LLMProvider):
    name = "scripted_pipeline"

    def __init__(self, script: Optional[List[ProviderResult]] = None) -> None:
        self._script = list(script) if script else []

    def complete(self, text, tools):
        if not self._script:
            return ProviderResult(text="default response", tool_calls=[])
        return self._script.pop(0)

    def feed_tool_results(self, results):
        pass


def make_pipeline(tmp_path, script=None):
    provider = ScriptedProvider(script)
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
        max_iterations=5,
    )
    router = IntentRouter(tools=registry.all())
    pipeline = Pipeline(agent=agent, router=router)
    return pipeline


def test_pipeline_conversational(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        [ProviderResult(text="Hello from pipeline", tool_calls=[])],
    )
    result = pipeline.execute("What is AI?")
    assert isinstance(result, PipelineResult)
    assert result.text == "Hello from pipeline"
    assert result.context.route_type == RouteType.CONVERSATIONAL.value
    assert result.error is None


def test_pipeline_tool_route(tmp_path):
    pipeline = make_pipeline(tmp_path)
    result = pipeline.execute("take a screenshot")
    assert result.context.route_type == RouteType.TOOL.value
    assert result.context.route_target == "take_screenshot"


def test_pipeline_unsupported_route(tmp_path):
    pipeline = make_pipeline(tmp_path)
    result = pipeline.execute("move mouse to 100,200")
    assert "cannot perform this action" in result.text.lower()
    assert result.context.route_type == RouteType.UNSUPPORTED.value


def test_pipeline_empty_input(tmp_path):
    pipeline = make_pipeline(tmp_path)
    result = pipeline.execute("")
    assert "valid request" in result.text.lower()
    assert result.error is not None


def test_pipeline_whitespace_input(tmp_path):
    pipeline = make_pipeline(tmp_path)
    result = pipeline.execute("   ")
    assert "valid request" in result.text.lower()


def test_pipeline_with_tool_execution(tmp_path):
    script = [
        ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="get_system_info", arguments={})]),
        ProviderResult(text="here is your system info", tool_calls=[]),
    ]
    pipeline = make_pipeline(tmp_path, script)
    result = pipeline.execute("get my system info")
    assert result.text == "here is your system info"
    assert len(result.events) == 1
    assert result.events[0].name == "get_system_info"


def test_pipeline_verification(tmp_path):
    script = [
        ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="get_system_info", arguments={})]),
        ProviderResult(text="done", tool_calls=[]),
    ]
    pipeline = make_pipeline(tmp_path, script)
    result = pipeline.execute("what is my system info")
    assert result.verification is not None
    assert result.verification.status == VerificationStatus.PASSED


def test_pipeline_verification_failure(tmp_path):
    script = [
        ProviderResult(text=None, tool_calls=[ToolCall(id="1", name="nope_tool", arguments={})]),
        ProviderResult(text="recovered", tool_calls=[]),
    ]
    pipeline = make_pipeline(tmp_path, script)
    result = pipeline.execute("run nope tool")
    assert result.verification is not None
    assert result.verification.status == VerificationStatus.FAILED


def test_pipeline_preserves_context(tmp_path):
    pipeline = make_pipeline(
        tmp_path,
        [ProviderResult(text="ok", tool_calls=[])],
    )
    ctx = RuntimeContext(conversation_id="sess1", metadata={"custom": True})
    result = pipeline.execute("hello", context=ctx)
    assert result.context.request_id == ctx.request_id
    assert result.context.conversation_id == "sess1"
    assert result.context.metadata["custom"] is True


def test_pipeline_error_handling(tmp_path):
    class FailingAgent(Agent):
        def run(self, user_text):
            raise RuntimeError("pipeline crash")

    provider = ScriptedProvider()
    audit = AuditLog(tmp_path / "audit.log")
    failing_agent = FailingAgent(provider=provider, tools=[], audit_log=audit, gate=PermissionGate())
    router = IntentRouter(tools=[])
    pipeline = Pipeline(agent=failing_agent, router=router)
    result = pipeline.execute("trigger error")
    assert "error" in result.text.lower()
    assert result.error is not None
    assert "RuntimeError" in result.error


def test_pipeline_plan_generation(tmp_path):
    pipeline = make_pipeline(tmp_path)
    result = pipeline.execute("take a screenshot")
    assert result.plan is not None
    assert len(result.plan.steps) == 1
    assert result.plan.steps[0].tool_name == "take_screenshot"
