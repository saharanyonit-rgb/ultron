"""Tests for specialized agents (ultron.agents)."""

from __future__ import annotations

from typing import List, Optional

from ultron.agents import AgentCapability, AgentRegistry, AgentSpec, BaseAgent
from ultron.agents.research import ResearchAgent
from ultron.agents.coding import CodingAgent
from ultron.agents.task import TaskAgent
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.tools import ALL_TOOLS


class FakeProvider(LLMProvider):
    """Scripted provider for testing."""

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


def test_agent_spec_creation():
    spec = AgentSpec(
        name="test_agent",
        description="Test agent",
        capabilities=[AgentCapability.RESEARCH],
        allowed_tools=["read_file"],
    )
    assert spec.name == "test_agent"
    assert AgentCapability.RESEARCH in spec.capabilities


def test_agent_registry_register():
    registry = AgentRegistry()
    provider = FakeProvider([ProviderResult(text="hello")])
    agent = ResearchAgent(provider, ALL_TOOLS)
    registry.register(agent)
    assert "research" in registry.list_names()


def test_agent_registry_select_by_capability():
    registry = AgentRegistry()
    provider = FakeProvider([ProviderResult(text="hello")])
    research_agent = ResearchAgent(provider, ALL_TOOLS)
    coding_agent = CodingAgent(provider, ALL_TOOLS)
    registry.register(research_agent)
    registry.register(coding_agent)

    selected = registry.select(AgentCapability.CODING)
    assert selected is not None
    assert selected.spec.name == "coding"


def test_research_agent_spec():
    provider = FakeProvider([ProviderResult(text="hello")])
    agent = ResearchAgent(provider, ALL_TOOLS)
    assert agent.spec.name == "research"
    assert AgentCapability.RESEARCH in agent.spec.capabilities
    assert "read_file" in agent.spec.allowed_tools


def test_coding_agent_spec():
    provider = FakeProvider([ProviderResult(text="hello")])
    agent = CodingAgent(provider, ALL_TOOLS)
    assert agent.spec.name == "coding"
    assert AgentCapability.CODING in agent.spec.capabilities
    assert "read_file" in agent.spec.allowed_tools
    assert "create_file" in agent.spec.allowed_tools


def test_task_agent_spec():
    provider = FakeProvider([ProviderResult(text="hello")])
    agent = TaskAgent(provider, ALL_TOOLS)
    assert agent.spec.name == "task"
    assert AgentCapability.TASK in agent.spec.capabilities
    assert AgentCapability.GENERAL in agent.spec.capabilities
    assert agent.spec.allowed_tools == []


def test_agent_allows_only_specified_tools():
    provider = FakeProvider([ProviderResult(text="hello")])
    agent = ResearchAgent(provider, ALL_TOOLS)
    tools = agent._get_tools()
    tool_names = [t.name for t in tools]
    assert "read_file" in tool_names
    assert "create_file" not in tool_names


def test_agent_registry_all():
    registry = AgentRegistry()
    provider = FakeProvider([ProviderResult(text="hello")])
    registry.register(ResearchAgent(provider, ALL_TOOLS))
    registry.register(CodingAgent(provider, ALL_TOOLS))
    registry.register(TaskAgent(provider, ALL_TOOLS))

    all_agents = registry.all()
    assert len(all_agents) == 3


def test_agent_registry_list_names():
    registry = AgentRegistry()
    provider = FakeProvider([ProviderResult(text="hello")])
    registry.register(ResearchAgent(provider, ALL_TOOLS))
    registry.register(CodingAgent(provider, ALL_TOOLS))

    names = registry.list_names()
    assert "research" in names
    assert "coding" in names


def test_agent_registry_empty():
    registry = AgentRegistry()
    assert len(registry.all()) == 0
    assert registry.list_names() == []
    assert registry.get("nonexistent") is None
    assert registry.select(AgentCapability.RESEARCH) is None


def test_research_agent_run():
    script = [
        ProviderResult(text="Research complete", tool_calls=[]),
    ]
    provider = FakeProvider(script)
    agent = ResearchAgent(provider, ALL_TOOLS)
    result = agent.run("research this topic")
    assert result == "Research complete"


def test_task_agent_run():
    script = [
        ProviderResult(text="Task done", tool_calls=[]),
    ]
    provider = FakeProvider(script)
    agent = TaskAgent(provider, ALL_TOOLS)
    result = agent.run("do this task")
    assert result == "Task done"
