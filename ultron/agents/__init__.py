"""Specialized agent architecture for JARVIS Phase 3.

Provides:
- BaseAgent: abstract base for specialized agents
- AgentRegistry: register/discover/select agents
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.tools import Tool


class AgentCapability(str, Enum):
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
    capabilities: List[AgentCapability]
    allowed_tools: List[str]
    max_iterations: int = 8


class BaseAgent(ABC):
    """Abstract base for specialized agents."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        spec: AgentSpec,
    ) -> None:
        self._provider = provider
        self._tools = {t.name: t for t in tools}
        self._spec = spec

    @property
    def spec(self) -> AgentSpec:
        return self._spec

    @abstractmethod
    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute the agent's specialized task."""
        ...

    def _get_tools(self) -> List[Tool]:
        """Get tools available to this agent."""
        if not self._spec.allowed_tools:
            return list(self._tools.values())
        return [self._tools[name] for name in self._spec.allowed_tools if name in self._tools]


class AgentRegistry:
    """Registry for discovering and selecting specialized agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.spec.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def select(self, capability: AgentCapability) -> Optional[BaseAgent]:
        """Select the best agent for a given capability."""
        for agent in self._agents.values():
            if capability in agent.spec.capabilities:
                return agent
        return None

    def all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def list_names(self) -> List[str]:
        return list(self._agents.keys())


__all__ = [
    "BaseAgent",
    "AgentCapability",
    "AgentSpec",
    "AgentRegistry",
]
