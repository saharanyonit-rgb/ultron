"""Specialized agent architecture for JARVIS Phase 3.

Provides:
- BaseAgent: abstract base for specialized agents
- AgentRegistry: register/discover/select agents
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.tools import Tool


class AgentCapability(StrEnum):
    RESEARCH = "research"
    CODING = "coding"
    TASK = "task"
    GENERAL = "general"
    VISION = "vision"


@dataclass
class AgentSpec:
    """Specification for a specialized agent."""

    name: str
    description: str
    capabilities: list[AgentCapability]
    allowed_tools: list[str]
    max_iterations: int = 8


class BaseAgent(ABC):
    """Abstract base for specialized agents."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[Tool],
        spec: AgentSpec,
    ) -> None:
        self._provider = provider
        self._tools = {t.name: t for t in tools}
        self._spec = spec

    @property
    def spec(self) -> AgentSpec:
        return self._spec

    @abstractmethod
    def run(self, user_text: str, context: dict[str, Any] | None = None) -> str:
        """Execute the agent's specialized task."""
        ...

    def _get_tools(self) -> list[Tool]:
        """Get tools available to this agent."""
        if not self._spec.allowed_tools:
            return list(self._tools.values())
        return [self._tools[name] for name in self._spec.allowed_tools if name in self._tools]


class AgentRegistry:
    """Registry for discovering and selecting specialized agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.spec.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def select(self, capability: AgentCapability) -> BaseAgent | None:
        """Select the best agent for a given capability."""
        for agent in self._agents.values():
            if capability in agent.spec.capabilities:
                return agent
        return None

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        return list(self._agents.keys())


__all__ = [
    "BaseAgent",
    "AgentCapability",
    "AgentSpec",
    "AgentRegistry",
    "ProviderResult",
    "ToolCall",
    "ToolResult",
]
