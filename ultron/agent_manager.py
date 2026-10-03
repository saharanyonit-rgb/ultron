"""Agent Manager and Communication Protocol for JARVIS Phase 5.

Extends the existing Phase 3 agent architecture with:
- Structured agent-to-agent communication
- Capability-based agent selection
- Agent availability tracking
- Message protocol for task coordination
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from ultron.agents import AgentCapability, AgentRegistry, BaseAgent

logger = logging.getLogger("ultron.agent_manager")


class MessageType(StrEnum):
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"
    TASK_UPDATE = "task_update"
    VERIFICATION_REQUEST = "verification_request"
    VERIFICATION_RESULT = "verification_result"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"
    CANCEL = "cancel"


@dataclass
class AgentMessage:
    """Structured message for agent-to-agent communication."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:10])
    message_type: MessageType = MessageType.TASK_REQUEST
    sender: str = ""
    receiver: str = ""
    task_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "task_id": self.task_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        return cls(
            id=data.get("id", str(uuid.uuid4())[:10]),
            message_type=MessageType(data.get("message_type", "task_request")),
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            task_id=data.get("task_id", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def task_request(
        cls,
        sender: str,
        receiver: str,
        task_id: str,
        task_description: str,
        task_input: dict[str, Any] | None = None,
    ) -> AgentMessage:
        return cls(
            message_type=MessageType.TASK_REQUEST,
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            payload={
                "description": task_description,
                "input": task_input or {},
            },
        )

    @classmethod
    def task_result(
        cls,
        sender: str,
        receiver: str,
        task_id: str,
        result: dict[str, Any],
    ) -> AgentMessage:
        return cls(
            message_type=MessageType.TASK_RESULT,
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            payload={"result": result},
        )

    @classmethod
    def task_error(
        cls,
        sender: str,
        receiver: str,
        task_id: str,
        error: str,
    ) -> AgentMessage:
        return cls(
            message_type=MessageType.TASK_ERROR,
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            payload={"error": error},
        )

    @classmethod
    def task_update(
        cls,
        sender: str,
        receiver: str,
        task_id: str,
        status: str,
        progress: float | None = None,
    ) -> AgentMessage:
        return cls(
            message_type=MessageType.TASK_UPDATE,
            sender=sender,
            receiver=receiver,
            task_id=task_id,
            payload={"status": status, "progress": progress},
        )


@dataclass
class AgentAvailability:
    """Tracks agent availability and workload."""

    agent_name: str
    is_available: bool = True
    current_task_id: str | None = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_active: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def success_rate(self) -> float:
        total = self.completed_tasks + self.failed_tasks
        if total == 0:
            return 1.0
        return self.completed_tasks / total


class AgentManager:
    """Manages agent selection, communication, and coordination.

    Extends the existing AgentRegistry with:
    - Capability-based selection
    - Availability tracking
    - Message routing
    - Load balancing
    """

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or AgentRegistry()
        self._availability: dict[str, AgentAvailability] = {}
        self._message_handlers: dict[
            MessageType, Callable[[AgentMessage], AgentMessage | None]
        ] = {}
        self._message_log: list[AgentMessage] = []

        for msg_type in MessageType:
            self._message_handlers[msg_type] = self._default_handler

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def message_log(self) -> list[AgentMessage]:
        return list(self._message_log)

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent and initialize availability tracking."""
        self._registry.register(agent)
        self._availability[agent.spec.name] = AgentAvailability(
            agent_name=agent.spec.name,
        )
        logger.info(
            "Registered agent: %s (capabilities=%s)", agent.spec.name, agent.spec.capabilities
        )

    def select_agent(
        self,
        required_capabilities: list[str],
        exclude_agents: list[str] | None = None,
    ) -> BaseAgent | None:
        """Select the best available agent for a set of capabilities."""
        exclude = set(exclude_agents or [])

        scored_agents: list[tuple[float, BaseAgent]] = []

        for agent in self._registry.all():
            if agent.spec.name in exclude:
                continue

            avail = self._availability.get(agent.spec.name)
            if avail and not avail.is_available:
                continue

            score = self._score_agent(agent, required_capabilities)
            if score > 0:
                scored_agents.append((score, agent))

        if not scored_agents:
            return None

        scored_agents.sort(key=lambda x: x[0], reverse=True)
        return scored_agents[0][1]

    def select_by_capability(self, capability: AgentCapability) -> BaseAgent | None:
        """Select an agent by a specific capability."""
        agent = self._registry.select(capability)
        if agent:
            avail = self._availability.get(agent.spec.name)
            if avail and not avail.is_available:
                return None
        return agent

    def mark_busy(self, agent_name: str, task_id: str) -> None:
        """Mark an agent as busy with a task."""
        avail = self._availability.get(agent_name)
        if avail:
            avail.is_available = False
            avail.current_task_id = task_id
            avail.last_active = datetime.now(UTC).isoformat()

    def mark_available(self, agent_name: str, success: bool = True) -> None:
        """Mark an agent as available after task completion."""
        avail = self._availability.get(agent_name)
        if avail:
            avail.is_available = True
            avail.current_task_id = None
            if success:
                avail.completed_tasks += 1
            else:
                avail.failed_tasks += 1
            avail.last_active = datetime.now(UTC).isoformat()

    def get_availability(self, agent_name: str) -> AgentAvailability | None:
        return self._availability.get(agent_name)

    def get_all_availability(self) -> dict[str, AgentAvailability]:
        return dict(self._availability)

    def send_message(self, message: AgentMessage) -> AgentMessage | None:
        """Send a message and get a response."""
        self._message_log.append(message)

        handler = self._message_handlers.get(message.message_type, self._default_handler)
        response = handler(message)

        if response:
            self._message_log.append(response)

        return response

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[AgentMessage], AgentMessage | None],
    ) -> None:
        """Register a custom message handler."""
        self._message_handlers[message_type] = handler

    def _score_agent(self, agent: BaseAgent, required_capabilities: list[str]) -> float:
        """Score an agent's suitability for a capability set."""
        if not required_capabilities:
            return 0.5

        agent_caps = {c.value if hasattr(c, "value") else str(c) for c in agent.spec.capabilities}
        required_set = set(required_capabilities)

        matched = agent_caps & required_set
        if not matched:
            return 0.0

        score = len(matched) / len(required_set)

        avail = self._availability.get(agent.spec.name)
        if avail:
            score *= avail.success_rate

        return score

    def _default_handler(self, message: AgentMessage) -> AgentMessage | None:
        """Default message handler."""
        logger.debug("Default handler for %s from %s", message.message_type.value, message.sender)
        return None


__all__ = [
    "MessageType",
    "AgentMessage",
    "AgentAvailability",
    "AgentManager",
]
