"""Tests for JARVIS Phase 7: Multi-Model Specialized Brain Architecture.

Tests cover:
- Model configuration
- Brain provider factory
- Brain router
- Specialized brains
- Brain orchestrator
- Agent integration
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from ultron.agents import AgentCapability
from ultron.brains import (
    BrainProviderFactory,
    BrainRouter,
    BrainType,
    BrainRouteDecision,
    PlanningBrain,
    ResearchBrain,
    CodingBrain,
    ComputerBrain,
    VerificationBrain,
    BrainOrchestrator,
    BrainContext,
    ExecutionPlan,
    PlannedTask,
    ResearchReport,
    CodingResult,
    ComputerResult,
    VerificationResult,
    VerificationStatus,
    VerificationRecommendation,
)
from ultron.config import (
    Config,
    LLMConfig,
    BrainConfig,
    BrainModelConfig,
)
from ultron.llm.base import LLMProvider, ProviderResult


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    name = "mock"

    def __init__(self) -> None:
        self._responses: list = []
        self._call_count = 0

    def add_response(self, text: str) -> None:
        self._responses.append(text)

    def complete(self, text, tools):
        self._call_count += 1
        if self._responses:
            response = self._responses.pop(0) if self._responses else ProviderResult(text="default")
            if isinstance(response, str):
                return ProviderResult(text=response)
            return response
        return ProviderResult(text=f"Response {self._call_count}")

    def feed_tool_results(self, results) -> None:
        pass


class TestBrainModelConfig:
    """Tests for brain model configuration."""

    def test_brain_model_config_defaults(self):
        config = BrainModelConfig()
        assert config.provider == "openrouter"
        assert config.model == "nvidia/nemotron-3-ultra-550b-a55b:free"
        assert config.temperature == 0.3
        assert config.max_tokens == 8192

    def test_brain_model_config_custom(self):
        config = BrainModelConfig(
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
            temperature=0.5,
            max_tokens=4096,
        )
        assert config.provider == "openrouter"
        assert config.model == "anthropic/claude-3.5-sonnet"
        assert config.temperature == 0.5
        assert config.max_tokens == 4096


class TestBrainConfig:
    """Tests for brain configuration."""

    def test_brain_config_defaults(self):
        config = BrainConfig()
        assert config.planning.provider == "openrouter"
        assert config.research.provider == "openrouter"
        assert config.coding.provider == "openrouter"
        assert config.computer.provider == "openrouter"
        assert config.verification.provider == "openrouter"
        assert config.fast.provider == "openrouter"

    def test_brain_config_independent(self):
        config = BrainConfig(
            planning=BrainModelConfig(provider="openrouter", model="planning-model"),
            research=BrainModelConfig(provider="gemini", model="research-model"),
        )
        assert config.planning.provider == "openrouter"
        assert config.planning.model == "planning-model"
        assert config.research.provider == "gemini"
        assert config.research.model == "research-model"


class TestBrainProviderFactory:
    """Tests for brain provider factory."""

    def test_factory_with_gemini(self):
        llm_config = LLMConfig(gemini_api_key="test-key")
        factory = BrainProviderFactory(llm_config)

        model_config = BrainModelConfig(provider="gemini", model="gemini-3.5-flash")
        provider = factory.create_provider(model_config)

        assert provider is not None
        assert provider.name == "gemini"

    def test_factory_with_openrouter(self):
        llm_config = LLMConfig(openrouter_api_key="test-key")
        factory = BrainProviderFactory(llm_config)

        model_config = BrainModelConfig(provider="openrouter", model="openai/gpt-4o")
        provider = factory.create_provider(model_config)

        assert provider is not None
        assert provider.name == "openrouter"

    def test_factory_missing_api_key(self):
        llm_config = LLMConfig(gemini_api_key="")
        factory = BrainProviderFactory(llm_config)

        model_config = BrainModelConfig(provider="gemini", model="gemini-3.5-flash")

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            factory.create_provider(model_config)


class TestBrainRouter:
    """Tests for brain router."""

    def test_router_initialization(self):
        router = BrainRouter()
        assert router is not None

    def test_route_research_request(self):
        router = BrainRouter()
        decision = router.route("Research the competitor analysis")

        assert decision.brain_type == BrainType.RESEARCH
        assert decision.confidence > 0.3

    def test_route_coding_request(self):
        router = BrainRouter()
        decision = router.route("Fix the login bug in the repository")

        assert decision.brain_type == BrainType.CODING
        assert decision.confidence > 0.4

    def test_route_computer_request(self):
        router = BrainRouter()
        decision = router.route("Open Chrome and navigate to google.com")

        assert decision.brain_type == BrainType.COMPUTER
        assert decision.confidence > 0.4

    def test_route_planning_request(self):
        router = BrainRouter()
        decision = router.route("Create a workflow with multiple steps to execute")

        assert decision.brain_type == BrainType.PLANNING
        assert decision.confidence > 0.4

    def test_route_verification_request(self):
        router = BrainRouter()
        decision = router.route("Verify and confirm that the task completed successfully and check the results")

        assert decision.brain_type == BrainType.VERIFICATION
        assert decision.confidence > 0.3

    def test_route_simple_conversational(self):
        router = BrainRouter()
        decision = router.route("Hello")

        assert decision.brain_type == BrainType.FAST
        assert decision.confidence > 0.5

    def test_should_use_planning_complex(self):
        router = BrainRouter()
        assert router.should_use_planning("research competitors and then create a report")
        assert router.should_use_planning("first do X, then do Y, after that do Z")

    def test_should_use_planning_simple(self):
        router = BrainRouter()
        assert not router.should_use_planning("hello")
        assert not router.should_use_planning("what time is it")


class TestPlanningBrain:
    """Tests for Planning Brain."""

    def test_planning_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_tools = []
        brain = PlanningBrain(mock_provider, mock_tools)

        assert brain.spec.name == "planning"
        assert brain.spec.max_iterations == 5
        assert AgentCapability.TASK in brain.spec.capabilities

    def test_planning_brain_parse_valid_json(self):
        mock_provider = MockLLMProvider()
        mock_provider.add_response(json.dumps({
            "goal": "Research and report",
            "tasks": [
                {"id": "task_1", "agent": "research", "description": "Research competitors", "dependencies": [], "parallel": True},
                {"id": "task_2", "agent": "fast", "description": "Write report", "dependencies": ["task_1"], "parallel": False},
            ],
            "reasoning": "Simple sequential plan",
        }))

        brain = PlanningBrain(mock_provider, [])
        plan = brain.plan("Research competitors and create a report")

        assert plan.goal == "Research and report"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].id == "task_1"
        assert plan.tasks[1].dependencies == ["task_1"]

    def test_planning_brain_get_parallel_groups(self):
        plan = ExecutionPlan(
            goal="Test",
            tasks=[
                PlannedTask(id="t1", agent="research", description="t1", dependencies=[], parallel=True),
                PlannedTask(id="t2", agent="coding", description="t2", dependencies=[], parallel=True),
                PlannedTask(id="t3", agent="fast", description="t3", dependencies=["t1", "t2"], parallel=False),
            ],
        )

        groups = plan.get_parallel_groups()
        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 1


class TestResearchBrain:
    """Tests for Research Brain."""

    def test_research_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_tools = []
        brain = ResearchBrain(mock_provider, mock_tools)

        assert brain.spec.name == "research"
        assert AgentCapability.RESEARCH in brain.spec.capabilities


class TestCodingBrain:
    """Tests for Coding Brain."""

    def test_coding_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_tools = []
        brain = CodingBrain(mock_provider, mock_tools)

        assert brain.spec.name == "coding"
        assert AgentCapability.CODING in brain.spec.capabilities


class TestComputerBrain:
    """Tests for Computer Brain."""

    def test_computer_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_tools = []
        brain = ComputerBrain(mock_provider, mock_tools)

        assert brain.spec.name == "computer"


class TestVerificationBrain:
    """Tests for Verification Brain."""

    def test_verification_brain_initialization(self):
        mock_provider = MockLLMProvider()
        mock_tools = []
        brain = VerificationBrain(mock_provider, mock_tools)

        assert brain.spec.name == "verification"

    def test_verification_result_to_dict(self):
        result = VerificationResult(
            status=VerificationStatus.PASSED,
            confidence=0.92,
            evidence=["Tool output shows success"],
            failures=[],
            recommendation=VerificationRecommendation.COMPLETE,
            reasoning="All checks passed",
        )

        data = result.to_dict()
        assert data["status"] == "passed"
        assert data["confidence"] == 0.92
        assert data["recommendation"] == "complete"


class TestBrainContext:
    """Tests for BrainContext."""

    def test_brain_context_creation(self):
        context = BrainContext(
            goal="Test goal",
            task="Test task",
            expected_outcome="Expected result",
            evidence=["Evidence 1", "Evidence 2"],
            metadata={"key": "value"},
        )

        assert context.goal == "Test goal"
        assert context.task == "Test task"
        assert context.expected_outcome == "Expected result"
        assert len(context.evidence) == 2
        assert context.metadata["key"] == "value"


class TestBrainOrchestrator:
    """Tests for BrainOrchestrator."""

    def test_orchestrator_initialization(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig()

        orchestrator = BrainOrchestrator(config, [])

        assert orchestrator is not None
        assert orchestrator._router is not None
        assert orchestrator._provider_factory is not None

    def test_orchestrator_get_brain_config(self):
        config = MagicMock(spec=Config)
        config.llm = LLMConfig(gemini_api_key="test-key", openrouter_api_key="test-key")
        config.brain = BrainConfig(
            planning=BrainModelConfig(provider="openrouter", model="planning-model"),
            research=BrainModelConfig(provider="gemini", model="research-model"),
        )

        orchestrator = BrainOrchestrator(config, [])

        planning_config = orchestrator._get_brain_config(BrainType.PLANNING)
        assert planning_config.provider == "openrouter"
        assert planning_config.model == "planning-model"

        research_config = orchestrator._get_brain_config(BrainType.RESEARCH)
        assert research_config.provider == "gemini"
        assert research_config.model == "research-model"


class TestVerificationStatus:
    """Tests for VerificationStatus enum."""

    def test_verification_status_values(self):
        assert VerificationStatus.PASSED.value == "passed"
        assert VerificationStatus.FAILED.value == "failed"
        assert VerificationStatus.INCONCLUSIVE.value == "inconclusive"


class TestVerificationRecommendation:
    """Tests for VerificationRecommendation enum."""

    def test_recommendation_values(self):
        assert VerificationRecommendation.COMPLETE.value == "complete"
        assert VerificationRecommendation.RETRY.value == "retry"
        assert VerificationRecommendation.REPLAN.value == "replan"
        assert VerificationRecommendation.SWITCH_AGENT.value == "switch_agent"
        assert VerificationRecommendation.ASK_USER.value == "ask_user"
        assert VerificationRecommendation.ABORT.value == "abort"


class TestBrainType:
    """Tests for BrainType enum."""

    def test_brain_type_values(self):
        assert BrainType.PLANNING.value == "planning"
        assert BrainType.RESEARCH.value == "research"
        assert BrainType.CODING.value == "coding"
        assert BrainType.COMPUTER.value == "computer"
        assert BrainType.VERIFICATION.value == "verification"
        assert BrainType.FAST.value == "fast"
        assert BrainType.GENERAL.value == "general"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
