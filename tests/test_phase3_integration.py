"""Integration tests for Phase 3 features."""

from __future__ import annotations

from typing import List, Optional

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.agents import AgentCapability, AgentRegistry
from ultron.agents.research import ResearchAgent
from ultron.agents.coding import CodingAgent
from ultron.agents.task import TaskAgent
from ultron.core.agent import Agent
from ultron.core.brain import Brain, BrainResponse, ResponseStatus, UserRequest
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.memory import Memory
from ultron.memory.semantic import SemanticMemory
from ultron.models import MemoryType, MultiStepPlanStep, PlanStepStatus
from ultron.planner import Planner, PlanExecutor
from ultron.tools import ALL_TOOLS, ToolRegistry
from ultron.verification import SemanticVerifier


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def __init__(self, script: Optional[List[ProviderResult]] = None) -> None:
        self._script = list(script) if script else []

    def complete(self, text: Optional[str], tools) -> ProviderResult:
        if not self._script:
            return ProviderResult(text="default response")
        return self._script.pop(0)

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        pass


def test_brain_with_semantic_memory(tmp_path):
    provider = ScriptedProvider([ProviderResult(text="Hello from Brain")])
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
        max_iterations=5,
    )
    memory = SemanticMemory(tmp_path / "memory.jsonl")
    brain = Brain(agent=agent, memory=memory)

    request = UserRequest(user_input="Hello Ultron")
    response = brain.process(request)

    assert response.status == ResponseStatus.SUCCESS
    assert memory.record_count >= 1


def test_brain_with_specialized_agents(tmp_path):
    provider = ScriptedProvider([ProviderResult(text="Agent response")])
    registry = AgentRegistry()
    registry.register(ResearchAgent(provider, ALL_TOOLS))
    registry.register(CodingAgent(provider, ALL_TOOLS))
    registry.register(TaskAgent(provider, ALL_TOOLS))

    research_agent = registry.select(AgentCapability.RESEARCH)
    assert research_agent is not None
    assert research_agent.spec.name == "research"


def test_end_to_end_research_task(tmp_path):
    script = [
        ProviderResult(text="Research complete: Found information about Python"),
    ]
    provider = FakeProvider(script)
    agent = ResearchAgent(provider, ALL_TOOLS)
    result = agent.run("research Python programming")
    assert "Research complete" in result


def test_end_to_end_coding_task(tmp_path):
    script = [
        ProviderResult(text="Coding task completed successfully"),
    ]
    provider = FakeProvider(script)
    agent = CodingAgent(provider, ALL_TOOLS)
    result = agent.run("analyze this code")
    assert "Coding task completed" in result


def test_plan_execution_pipeline(tmp_path):
    def mock_executor(tool_name, args):
        from ultron.models import ExecutionResult, ExecutionStatus
        return ExecutionResult(
            tool_name=tool_name,
            status=ExecutionStatus.SUCCESS,
            output={"result": "ok"},
        )

    planner = Planner()
    steps = [
        MultiStepPlanStep(tool_name="read_file", objective="read config"),
        MultiStepPlanStep(tool_name="create_file", objective="write output"),
    ]
    plan = planner.create_plan(steps)

    executor = PlanExecutor(mock_executor)
    result = executor.execute_plan(plan)

    assert len(result.completed_steps()) == 2


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, script: List[ProviderResult]) -> None:
        self._script = list(script)
        self.calls = 0

    def complete(self, text: Optional[str], tools) -> ProviderResult:
        self.calls += 1
        if not self._script:
            return ProviderResult(text="(no more steps)")
        return self._script.pop(0)

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        pass
