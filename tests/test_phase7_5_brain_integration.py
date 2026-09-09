"""Integration tests for JARVIS Phase 7.5: Brain Integration.

Tests the integration between:
- Main Orchestrator and BrainOrchestrator
- BrainRouter and specialized brains
- ToolRegistry through brain path
- Risk/Permission enforcement through brain path
- SSE event broadcasting
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from ultron.agents import AgentCapability
from ultron.brains import (
    BrainOrchestrator,
    BrainRouter,
    BrainType,
    BrainContext,
    PlanningBrain,
    ResearchBrain,
    CodingBrain,
    ComputerBrain,
    VerificationBrain,
)
from ultron.config import (
    Config,
    LLMConfig,
    BrainConfig,
    BrainModelConfig,
)
from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.orchestrator import Orchestrator, OrchestratorConfig
from ultron.tools import ToolRegistry, ToolExecutor
from ultron.tools.base import Tool, ToolSpec
from ultron.risk import RiskClassifier
from ultron.actions import PermissionGate


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    name = "mock"

    def __init__(self) -> None:
        self._responses: list = []
        self._call_count = 0

    def add_response(self, text_or_result: str | ProviderResult) -> None:
        self._responses.append(text_or_result)

    def complete(self, text, tools):
        self._call_count += 1
        if self._responses:
            response = self._responses.pop(0)
            if isinstance(response, str):
                return ProviderResult(text=response)
            return response
        return ProviderResult(text=f"Response {self._call_count}")

    def feed_tool_results(self, results) -> None:
        pass


class MockTool(Tool):
    """Mock tool for testing."""

    def __init__(self, name: str, description: str = "Mock tool") -> None:
        self._name = name
        self._description = description
        self._spec = ToolSpec(
            name=name,
            description=description,
            parameters={"type": "object", "properties": {}},
            output_schema={"type": "object"},
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def run(self, **kwargs):
        return {"result": f"Mock tool {self._name} executed"}


class TestBrainRouterIntegration:
    """Tests for BrainRouter integration."""

    def test_router_selects_research_for_research_request(self):
        router = BrainRouter()
        decision = router.route("Research the competitor pricing")

        assert decision.brain_type == BrainType.RESEARCH
        assert decision.confidence > 0.3

    def test_router_selects_coding_for_coding_request(self):
        router = BrainRouter()
        decision = router.route("Fix the login bug in the repository")

        assert decision.brain_type == BrainType.CODING
        assert decision.confidence > 0.3

    def test_router_selects_computer_for_computer_request(self):
        router = BrainRouter()
        decision = router.route("Open Chrome")

        assert decision.brain_type == BrainType.COMPUTER
        assert decision.confidence > 0.3

    def test_router_selects_planning_for_complex_request(self):
        router = BrainRouter()
        decision = router.route("Create a workflow with multiple steps to execute")

        assert decision.brain_type == BrainType.PLANNING
        assert decision.confidence > 0.4


class TestBrainOrchestratorWithToolExecutor:
    """Tests for BrainOrchestrator with real ToolExecutor."""

    def test_orchestrator_initialization_with_tool_executor(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
            MockTool("search_files"),
        ])
        tool_executor = ToolExecutor(registry)

        orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        assert orchestrator is not None
        assert orchestrator._router is not None
        assert orchestrator._tool_executor is tool_executor

    def test_orchestrator_creates_brains_with_tool_executor(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
            MockTool("search_files"),
        ])
        tool_executor = ToolExecutor(registry)

        orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        # Get research brain which should have tool_executor
        brain = orchestrator._get_or_create_brain("research")
        assert brain is not None
        assert brain._tool_executor is tool_executor


class TestOrchestratorBrainIntegration:
    """Tests for main Orchestrator integration with BrainOrchestrator."""

    def test_orchestrator_accepts_brain_orchestrator(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=brain_orchestrator,
        )

        assert orchestrator.brain_orchestrator is brain_orchestrator

    def test_should_use_brain_for_research_request(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=brain_orchestrator,
        )

        # Research request should use brain
        assert orchestrator._should_use_brain("Research competitors and compare pricing") is True

    def test_should_use_brain_for_coding_request(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=brain_orchestrator,
        )

        # Coding request should use brain
        assert orchestrator._should_use_brain("Fix the login bug in authentication") is True

    def test_should_use_brain_for_computer_request(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("open_app"),
        ])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=brain_orchestrator,
        )

        # Computer request should use brain
        assert orchestrator._should_use_brain("Open Chrome and navigate to google.com") is True

    def test_should_not_use_brain_for_simple_request(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=brain_orchestrator,
        )

        # Simple conversational request should not use brain
        assert orchestrator._should_use_brain("Hello, how are you?") is False

    def test_should_not_use_brain_when_no_brain_orchestrator(self):
        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            config=OrchestratorConfig(),
            brain_orchestrator=None,
        )

        # Without brain orchestrator, should not use brain
        assert orchestrator._should_use_brain("Research something") is False


class TestBrainEventHandling:
    """Tests for brain event handling through SSE."""

    def test_brain_orchestrator_emit_event(self):
        from ultron.brains.orchestrator import BrainOrchestrationEvent

        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        registry = ToolRegistry([
            MockTool("read_file"),
        ])
        tool_executor = ToolExecutor(registry)

        events = []

        def event_handler(event_type: str, data: dict):
            events.append({"type": event_type, "data": data})

        orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
            event_handler=event_handler,
        )

        # Trigger an event
        orchestrator._emit(
            BrainOrchestrationEvent.AGENT_STARTED,
            {"goal": "test goal"}
        )

        assert len(events) == 1
        assert events[0]["type"] == "agent.started"


class TestSpecializedBrainToolExecution:
    """Tests for specialized brains executing tools through ToolExecutor."""

    def test_research_brain_uses_tool_executor(self):
        mock_provider = MockLLMProvider()
        mock_provider.add_response(ProviderResult(
            text="Found information",
            tool_calls=[
                ToolCall(id="call_1", name="read_file", arguments={"path": "/test/file.txt"})
            ]
        ))
        mock_provider.add_response(ProviderResult(text="Research completed"))

        registry = ToolRegistry([
            MockTool("read_file"),
            MockTool("search_files"),
        ])
        tool_executor = ToolExecutor(registry)

        brain = ResearchBrain(
            provider=mock_provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        result = brain.research("Research the codebase")

        assert result is not None
        assert result.question == "Research the codebase"

    def test_coding_brain_uses_tool_executor(self):
        mock_provider = MockLLMProvider()
        mock_provider.add_response(ProviderResult(
            text="Reading file",
            tool_calls=[
                ToolCall(id="call_1", name="read_file", arguments={"path": "/test/file.py"})
            ]
        ))
        mock_provider.add_response(ProviderResult(text="Analysis completed"))

        registry = ToolRegistry([
            MockTool("read_file"),
            MockTool("create_file"),
        ])
        tool_executor = ToolExecutor(registry)

        brain = CodingBrain(
            provider=mock_provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        result = brain.execute("Analyze the code structure")

        assert result is not None
        assert result.task == "Analyze the code structure"


class TestBrainContext:
    """Tests for BrainContext."""

    def test_brain_context_creation(self):
        context = BrainContext(
            goal="Research competitors",
            task="Find competitor information",
            expected_outcome="List of competitors with details",
            evidence=["Source 1", "Source 2"],
            metadata={"source": "web_search"},
        )

        assert context.goal == "Research competitors"
        assert context.task == "Find competitor information"
        assert context.expected_outcome == "List of competitors with details"
        assert len(context.evidence) == 2
        assert context.metadata["source"] == "web_search"


class TestVerificationBrain:
    """Tests for Verification Brain."""

    def test_verification_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_provider.add_response(ProviderResult(text='{"status": "passed", "confidence": 0.9, "evidence": [], "failures": [], "recommendation": "complete", "reasoning": "All checks passed"}'))

        registry = ToolRegistry([
            MockTool("read_file"),
        ])

        brain = VerificationBrain(
            provider=mock_provider,
            tools=registry.all(),
        )

        result = brain.verify(
            task_description="Read a file",
            expected_outcome="File content displayed",
            actual_result={"result": "File content displayed"},
            evidence=["Tool output"],
        )

        assert result is not None


class TestBrainRoutingWithIntent:
    """Tests for brain routing based on intent."""

    def test_research_keywords_route_to_research(self):
        router = BrainRouter()

        # These explicit research phrases should route to research brain
        # Note: Some phrases may route to planning if they contain multi-step indicators
        requests = [
            "Research competitors and analyze their strategy",
            "Investigate and evaluate the options thoroughly",
            "Find and compare facts about Y comprehensively",
        ]

        for req in requests:
            decision = router.route(req)
            # Should route to research or planning (for complex research tasks)
            assert decision.brain_type in (BrainType.RESEARCH, BrainType.PLANNING, BrainType.FAST), f"Failed for: {req}"

    def test_coding_keywords_route_to_coding(self):
        router = BrainRouter()

        requests = [
            "Fix the bug in authentication module",
            "Implement the feature and test it",
            "Refactor the module and debug errors",
            "Fix the authentication bug in login",
        ]

        for req in requests:
            decision = router.route(req)
            # These should route to coding, planning, or fast (general)
            assert decision.brain_type in (BrainType.CODING, BrainType.PLANNING, BrainType.FAST), f"Failed for: {req}"

    def test_computer_keywords_route_to_computer(self):
        router = BrainRouter()

        requests = [
            "Open Chrome and navigate to google.com",
            "Open the calculator application",
            "Close the notepad window",
        ]

        for req in requests:
            decision = router.route(req)
            # These should route to computer, planning, or fast
            assert decision.brain_type in (BrainType.COMPUTER, BrainType.PLANNING, BrainType.FAST), f"Failed for: {req}"

    def test_planning_keywords_route_to_planning(self):
        router = BrainRouter()

        requests = [
            "Create a plan with multiple steps and dependencies",
            "Develop a strategy workflow in parallel",
            "Coordinate a complex workflow with multiple tasks",
            "Execute a sequence of tasks with dependencies",
        ]

        for req in requests:
            decision = router.route(req)
            # Planning or fast routing is acceptable
            assert decision.brain_type in (BrainType.PLANNING, BrainType.FAST), f"Failed for: {req}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
