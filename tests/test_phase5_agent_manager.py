"""Tests for Phase 5.4: Agent Manager and Communication Protocol."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from ultron.agent_manager import AgentAvailability, AgentManager, AgentMessage, MessageType
from ultron.agents import AgentCapability, AgentSpec, BaseAgent


class MockAgent(BaseAgent):
    """Minimal agent implementation for testing."""

    def __init__(self, name: str, caps: List[AgentCapability], tools: Optional[List[str]] = None):
        spec = AgentSpec(
            name=name,
            description=f"Mock {name} agent",
            capabilities=caps,
            allowed_tools=tools or [],
        )
        provider = MagicMock()
        super().__init__(provider, [], spec)

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        return f"Executed: {user_text}"


class TestAgentMessage:
    def test_message_creation(self):
        msg = AgentMessage(
            message_type=MessageType.TASK_REQUEST,
            sender="orchestrator",
            receiver="research",
            task_id="t1",
            payload={"description": "research something"},
        )
        assert msg.sender == "orchestrator"
        assert msg.receiver == "research"

    def test_message_serialization(self):
        msg = AgentMessage(
            message_type=MessageType.TASK_RESULT,
            sender="agent1",
            receiver="orchestrator",
            task_id="t1",
            payload={"result": "done"},
        )
        d = msg.to_dict()
        restored = AgentMessage.from_dict(d)
        assert restored.message_type == MessageType.TASK_RESULT
        assert restored.payload["result"] == "done"

    def test_task_request_factory(self):
        msg = AgentMessage.task_request(
            sender="orch",
            receiver="agent",
            task_id="t1",
            task_description="do work",
            task_input={"data": 42},
        )
        assert msg.message_type == MessageType.TASK_REQUEST
        assert msg.payload["description"] == "do work"

    def test_task_result_factory(self):
        msg = AgentMessage.task_result(
            sender="agent",
            receiver="orch",
            task_id="t1",
            result={"output": "value"},
        )
        assert msg.message_type == MessageType.TASK_RESULT

    def test_task_error_factory(self):
        msg = AgentMessage.task_error(
            sender="agent",
            receiver="orch",
            task_id="t1",
            error="something broke",
        )
        assert msg.payload["error"] == "something broke"


class TestAgentAvailability:
    def test_availability_defaults(self):
        avail = AgentAvailability(agent_name="test")
        assert avail.is_available
        assert avail.completed_tasks == 0
        assert avail.success_rate == 1.0

    def test_success_rate(self):
        avail = AgentAvailability(agent_name="test")
        avail.completed_tasks = 8
        avail.failed_tasks = 2
        assert avail.success_rate == 0.8


class TestAgentManager:
    def test_register_agent(self):
        manager = AgentManager()
        agent = MockAgent("test", [AgentCapability.RESEARCH])
        manager.register_agent(agent)
        assert manager.registry.get("test") is agent

    def test_select_agent_by_capability(self):
        manager = AgentManager()
        research = MockAgent("research", [AgentCapability.RESEARCH])
        coding = MockAgent("coding", [AgentCapability.CODING])
        manager.register_agent(research)
        manager.register_agent(coding)

        selected = manager.select_agent(["research"])
        assert selected is not None
        assert selected.spec.name == "research"

    def test_select_agent_multiple_capabilities(self):
        manager = AgentManager()
        research = MockAgent("research", [AgentCapability.RESEARCH])
        coding = MockAgent("coding", [AgentCapability.CODING])
        manager.register_agent(research)
        manager.register_agent(coding)

        selected = manager.select_agent(["research", "coding"])
        assert selected is not None
        assert selected.spec.name in ("research", "coding")

    def test_select_agent_unavailable(self):
        manager = AgentManager()
        agent = MockAgent("test", [AgentCapability.RESEARCH])
        manager.register_agent(agent)
        manager.mark_busy("test", "t1")

        selected = manager.select_agent(["research"])
        assert selected is None

    def test_select_agent_becomes_available(self):
        manager = AgentManager()
        agent = MockAgent("test", [AgentCapability.RESEARCH])
        manager.register_agent(agent)
        manager.mark_busy("test", "t1")
        manager.mark_available("test", True)

        selected = manager.select_agent(["research"])
        assert selected is not None

    def test_select_by_capability(self):
        manager = AgentManager()
        agent = MockAgent("research", [AgentCapability.RESEARCH])
        manager.register_agent(agent)

        selected = manager.select_by_capability(AgentCapability.RESEARCH)
        assert selected is not None

    def test_availability_tracking(self):
        manager = AgentManager()
        agent = MockAgent("test", [AgentCapability.RESEARCH])
        manager.register_agent(agent)

        avail = manager.get_availability("test")
        assert avail is not None
        assert avail.is_available

        manager.mark_busy("test", "t1")
        avail = manager.get_availability("test")
        assert not avail.is_available

        manager.mark_available("test", True)
        avail = manager.get_availability("test")
        assert avail.is_available
        assert avail.completed_tasks == 1

    def test_mark_available_failure(self):
        manager = AgentManager()
        agent = MockAgent("test", [AgentCapability.RESEARCH])
        manager.register_agent(agent)
        manager.mark_busy("test", "t1")
        manager.mark_available("test", False)

        avail = manager.get_availability("test")
        assert avail.failed_tasks == 1

    def test_send_message(self):
        manager = AgentManager()
        msg = AgentMessage(
            message_type=MessageType.TASK_REQUEST,
            sender="orch",
            receiver="agent",
            task_id="t1",
        )
        response = manager.send_message(msg)
        assert len(manager.message_log) == 1

    def test_custom_handler(self):
        manager = AgentManager()

        def handler(msg: AgentMessage) -> Optional[AgentMessage]:
            return AgentMessage.task_result(
                sender=msg.receiver,
                receiver=msg.sender,
                task_id=msg.task_id,
                result={"handled": True},
            )

        manager.register_handler(MessageType.TASK_REQUEST, handler)
        msg = AgentMessage.task_request("orch", "agent", "t1", "do work")
        response = manager.send_message(msg)
        assert response is not None
        assert response.message_type == MessageType.TASK_RESULT

    def test_exclude_agents(self):
        manager = AgentManager()
        a1 = MockAgent("a1", [AgentCapability.RESEARCH])
        a2 = MockAgent("a2", [AgentCapability.RESEARCH])
        manager.register_agent(a1)
        manager.register_agent(a2)

        selected = manager.select_agent(["research"], exclude_agents=["a1"])
        assert selected is not None
        assert selected.spec.name == "a2"

    def test_get_all_availability(self):
        manager = AgentManager()
        a1 = MockAgent("a1", [AgentCapability.RESEARCH])
        a2 = MockAgent("a2", [AgentCapability.CODING])
        manager.register_agent(a1)
        manager.register_agent(a2)

        all_avail = manager.get_all_availability()
        assert len(all_avail) == 2
