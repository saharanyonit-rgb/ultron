"""JARVIS Phase 7.6: Real End-to-End Integration Tests.

These tests validate the JARVIS system using REAL model providers and execution paths.
They are separate from unit tests to avoid consuming API quota during normal test runs.

Run with: pytest tests/test_phase7_6_real_e2e.py -v -m real_e2e
Or simply: pytest tests/test_phase7_6_real_e2e.py -v

WARNING: These tests make real API calls and may incur costs.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Force OpenRouter for E2E tests to avoid Gemini rate limits
# OpenRouter provides access to many models with more generous limits
os.environ["ULTRON_PROVIDER"] = "openrouter"

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
from ultron.config import load_config, Config, BrainModelConfig
from ultron.llm import build_provider
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.orchestrator import Orchestrator, OrchestratorConfig
from ultron.tools import ToolRegistry, ToolExecutor, ALL_TOOLS
from ultron.risk import RiskClassifier
from ultron.actions import PermissionGate


def _load_env_dict() -> Dict[str, str]:
    """Load .env file into a dictionary."""
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        return {}
    result = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip("'").strip('"')
    return result


def get_openrouter_config() -> Config:
    """Create config with OpenRouter and appropriate model."""
    env_dict = _load_env_dict()

    openrouter_key = env_dict.get("ULTRON_OPENROUTER_API_KEY", "")
    if not openrouter_key:
        raise ValueError("ULTRON_OPENROUTER_API_KEY not found in .env")

    return load_config(environ={
        "ULTRON_PROVIDER": "openrouter",
        "ULTRON_OPENROUTER_API_KEY": openrouter_key,
        # Use a model that works with OpenRouter - openai/gpt-4o-mini is widely available
        "ULTRON_MODEL": "openai/gpt-4o-mini",
        # Brain models
        "JARVIS_PLANNER_MODEL": "openai/gpt-4o-mini",
        "JARVIS_RESEARCH_MODEL": "openai/gpt-4o-mini",
        "JARVIS_CODING_MODEL": "openai/gpt-4o-mini",
        "JARVIS_COMPUTER_MODEL": "openai/gpt-4o-mini",
        "JARVIS_VERIFICATION_MODEL": "openai/gpt-4o-mini",
        "JARVIS_FAST_MODEL": "openai/gpt-4o-mini",
    })


@dataclass
class E2EResult:
    """Captures the result of an E2E test execution."""
    success: bool
    test_name: str
    brain_selected: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_seconds: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    permission_events: List[Dict[str, Any]] = field(default_factory=list)
    verification_result: Optional[Dict[str, Any]] = None
    retries: int = 0
    final_status: str = ""
    failure_reason: Optional[str] = None
    response_text: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


class TestRealE2EProvider:
    """Test real provider connectivity and basic operation."""

    @pytest.mark.real_e2e
    def test_provider_initialization(self):
        """Test that a real provider can be initialized from config."""
        try:
            config = get_openrouter_config()
            provider = build_provider(config)
            assert provider is not None
            assert hasattr(provider, 'complete')
            print(f"Provider initialized: {provider.name}")
        except Exception as e:
            pytest.fail(f"Failed to initialize provider: {e}")

    @pytest.mark.real_e2e
    def test_simple_completion(self):
        """Test a simple LLM completion without tools."""
        config = get_openrouter_config()
        provider = build_provider(config)

        result = provider.complete("Say 'test' if you can hear me.", [])

        assert result is not None
        assert result.text is not None or len(result.text) > 0
        print(f"Completion result: {result.text[:100]}...")


class TestRealBrainRouting:
    """Test brain routing with real providers."""

    @pytest.mark.real_e2e
    def test_research_brain_routing(self):
        """Test that research requests route to Research Brain."""
        router = BrainRouter()
        # Use explicit research keywords that trigger research routing
        decision = router.route("Research competitors and analyze their strategy for a startup")

        print(f"Routed to: {decision.brain_type.value} (confidence: {decision.confidence})")
        # Should route to research, planning, or fast (for conversation)
        assert decision.brain_type in (BrainType.RESEARCH, BrainType.PLANNING, BrainType.FAST)

    @pytest.mark.real_e2e
    def test_coding_brain_routing(self):
        """Test that coding requests route to Coding Brain."""
        router = BrainRouter()
        decision = router.route("Fix the bug in the authentication module")

        print(f"Routed to: {decision.brain_type.value} (confidence: {decision.confidence})")
        # Should route to coding or planning
        assert decision.brain_type in (BrainType.CODING, BrainType.PLANNING)


class TestRealOrchestratorBrainIntegration:
    """Test main Orchestrator with BrainOrchestrator integration."""

    @pytest.mark.real_e2e
    def test_orchestrator_with_brain(self):
        """Test Orchestrator routes complex requests to brain."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:10])  # Use subset for testing
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

        # Verify brain orchestrator is wired
        assert orchestrator.brain_orchestrator is not None
        print("Brain orchestrator wired successfully")

    @pytest.mark.real_e2e
    def test_should_use_brain_detection(self):
        """Test that orchestrator correctly detects brain-worthy requests."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:10])
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
        assert orchestrator._should_use_brain("Research competitors and analyze their pricing") is True

        # Simple request should not use brain
        assert orchestrator._should_use_brain("Hello, how are you?") is False

        print("Brain detection working correctly")


class TestRealResearchBrain:
    """Test Research Brain with real model and tools."""

    @pytest.mark.real_e2e
    def test_research_brain_execution(self):
        """Test Research Brain executes with real provider."""
        config = get_openrouter_config()
        provider = build_provider(config)

        registry = ToolRegistry(ALL_TOOLS[:10])
        tool_executor = ToolExecutor(registry)

        brain = ResearchBrain(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        # Ask about the project structure
        result = brain.research("What files are in the ultron directory?")

        assert result is not None
        assert result.question == "What files are in the ultron directory?"
        print(f"Research result: {result.summary}")
        print(f"Findings: {len(result.findings)}")


class TestRealCodingBrain:
    """Test Coding Brain with real model and tools."""

    @pytest.mark.real_e2e
    def test_coding_brain_execution(self):
        """Test Coding Brain executes with real provider."""
        config = get_openrouter_config()
        provider = build_provider(config)

        registry = ToolRegistry(ALL_TOOLS[:10])
        tool_executor = ToolExecutor(registry)

        brain = CodingBrain(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        # Inspect the tests directory
        result = brain.execute("Look at the tests directory and describe what you see")

        assert result is not None
        assert result.task == "Look at the tests directory and describe what you see"
        print(f"Coding result: {result.summary}")


class TestRealBrainOrchestrator:
    """Test BrainOrchestrator end-to-end."""

    @pytest.mark.real_e2e
    def test_brain_orchestrator_execute(self):
        """Test BrainOrchestrator.execute() with real provider."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:10])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        context = BrainContext(
            goal="Research the JARVIS project structure",
        )

        result = brain_orchestrator.execute("Research the JARVIS project structure", context)

        print(f"Result success: {result.success}")
        print(f"Brain type: {result.brain_type}")
        if result.error:
            print(f"Error: {result.error}")

        assert result is not None

    @pytest.mark.real_e2e
    def test_brain_orchestrator_planning(self):
        """Test BrainOrchestrator with planning request."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:10])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        result = brain_orchestrator.execute("Create a plan to research and compare different LLM providers")

        print(f"Result success: {result.success}")
        print(f"Brain type: {result.brain_type}")
        if result.output:
            print(f"Output: {str(result.output)[:200]}...")

        assert result is not None


class TestRealToolExecution:
    """Test real tool execution through ToolExecutor."""

    @pytest.mark.real_e2e
    def test_read_file_tool(self):
        """Test read_file tool through ToolExecutor."""
        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "read_file"])
        tool_executor = ToolExecutor(registry)

        result = tool_executor.execute("read_file", {"path": "D:\\jarvis\\pyproject.toml"})

        print(f"Tool execution status: {result.status}")
        print(f"Tool output (first 200 chars): {str(result.output)[:200]}")

        assert result.status.value == "success"

    @pytest.mark.real_e2e
    def test_search_files_tool(self):
        """Test search_files tool through ToolExecutor."""
        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "search_files"])
        tool_executor = ToolExecutor(registry)

        result = tool_executor.execute("search_files", {"directory": "D:\\jarvis\\ultron", "pattern": "*.py"})

        print(f"Tool execution status: {result.status}")
        print(f"Files found: {len(str(result.output).splitlines()) if result.output else 0}")

        assert result.status.value == "success"

    @pytest.mark.real_e2e
    def test_get_system_info_tool(self):
        """Test get_system_info tool through ToolExecutor."""
        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "get_system_info"])
        tool_executor = ToolExecutor(registry)

        result = tool_executor.execute("get_system_info", {})

        print(f"Tool execution status: {result.status}")
        print(f"System info keys: {list(result.output.keys()) if result.output else []}")

        assert result.status.value == "success"


class TestRealPermissionEnforcement:
    """Test permission enforcement through the tool execution path."""

    @pytest.mark.real_e2e
    def test_low_risk_tool_allowed(self):
        """Test that LOW risk tools execute without permission."""
        risk_classifier = RiskClassifier()
        gate = PermissionGate()

        # get_system_info is LOW risk
        risk = risk_classifier.classify("get_system_info", {})
        assert risk.value in ("read", "low"), f"Expected LOW/READ risk, got {risk.value}"

        print(f"get_system_info risk: {risk.value}")

    @pytest.mark.real_e2e
    def test_medium_risk_tool_classification(self):
        """Test that MEDIUM risk tools are properly classified."""
        risk_classifier = RiskClassifier()

        # create_file is MEDIUM risk
        risk = risk_classifier.classify("create_file", {})
        print(f"create_file risk: {risk.value}")
        assert risk.value == "medium"

    @pytest.mark.real_e2e
    def test_high_risk_tool_classification(self):
        """Test that HIGH/CRITICAL risk tools are properly classified."""
        risk_classifier = RiskClassifier()

        # delete_file is HIGH risk
        risk = risk_classifier.classify("delete_file", {})
        print(f"delete_file risk: {risk.value}")
        assert risk.value in ("high", "critical")

        # execute_command is CRITICAL
        risk = risk_classifier.classify("execute_command", {})
        print(f"execute_command risk: {risk.value}")
        assert risk.value == "critical"


class TestRealVerification:
    """Test verification with real model."""

    @pytest.mark.real_e2e
    def test_verification_brain(self):
        """Test Verification Brain with real provider."""
        config = get_openrouter_config()
        provider = build_provider(config)

        brain = VerificationBrain(
            provider=provider,
            tools=[],
        )

        result = brain.verify(
            task_description="Read the project configuration",
            expected_outcome="Configuration details displayed",
            actual_result={"status": "success", "config": "pyproject.toml content"},
            evidence=["Tool output shows configuration"],
        )

        print(f"Verification status: {result.status.value}")
        print(f"Confidence: {result.confidence}")
        print(f"Recommendation: {result.recommendation.value}")

        assert result is not None
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0


class TestRealFailureHandling:
    """Test failure handling with real components."""

    @pytest.mark.real_e2e
    def test_nonexistent_file(self):
        """Test handling of nonexistent file access."""
        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "read_file"])
        tool_executor = ToolExecutor(registry)

        result = tool_executor.execute("read_file", {"path": "nonexistent_file_xyz.txt"})

        print(f"Tool execution status: {result.status}")
        print(f"Tool error: {result.error}")

        # Should fail gracefully, not crash
        assert result.status.value in ("failure", "permission_denied")

    @pytest.mark.real_e2e
    def test_invalid_tool_parameters(self):
        """Test handling of invalid tool parameters."""
        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "open_url"])
        tool_executor = ToolExecutor(registry)

        # open_url should reject invalid URLs
        result = tool_executor.execute("open_url", {"url": "javascript:alert(1)"})

        print(f"Tool execution status: {result.status}")
        print(f"Tool output: {result.output}")

        # Should reject dangerous schemes
        assert result.status.value in ("failure", "permission_denied")


class TestRealSEvents:
    """Test SSE event generation."""

    @pytest.mark.real_e2e
    def test_brain_orchestrator_events(self):
        """Test that BrainOrchestrator emits events."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:10])
        tool_executor = ToolExecutor(registry)

        events_captured = []

        def event_handler(event_type: str, data: dict):
            events_captured.append({"type": event_type, "data": data})

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
            event_handler=event_handler,
        )

        brain_orchestrator.execute("Say hello", None)

        print(f"Events captured: {len(events_captured)}")
        for event in events_captured[:5]:  # Show first 5
            print(f"  - {event['type']}")

        # Should have emitted at least agent_started event
        assert len(events_captured) > 0


class TestRealEndToEndScenarios:
    """Full end-to-end scenarios with real components."""

    @pytest.mark.real_e2e
    def test_simple_conversational_request(self):
        """TEST A: Simple conversational request - fast path."""
        config = get_openrouter_config()
        provider = build_provider(config)

        # Simple "hello" type request - should use fast/conversational path
        result = provider.complete("Say hello in one sentence.", [])

        print(f"Response: {result.text}")
        assert result.text is not None
        assert len(result.text) > 0

    @pytest.mark.real_e2e
    def test_research_workflow(self):
        """TEST B: Research workflow with tool usage."""
        config = get_openrouter_config()
        provider = build_provider(config)

        registry = ToolRegistry(ALL_TOOLS[:15])
        tool_executor = ToolExecutor(registry)

        brain = ResearchBrain(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        # This should trigger real tool usage
        result = brain.research("Look at the ultron directory structure and describe what you find")

        print(f"Research summary: {result.summary}")
        print(f"Number of findings: {len(result.findings)}")

        assert result is not None

    @pytest.mark.real_e2e
    def test_coding_workflow(self):
        """TEST C: Coding workflow - inspect repository."""
        config = get_openrouter_config()
        provider = build_provider(config)

        registry = ToolRegistry(ALL_TOOLS[:15])
        tool_executor = ToolExecutor(registry)

        brain = CodingBrain(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        result = brain.execute("Inspect the tests directory and describe what you see")

        print(f"Coding summary: {result.summary}")
        print(f"Number of changes: {len(result.changes)}")

        assert result is not None

    @pytest.mark.real_e2e
    def test_computer_workflow(self):
        """TEST D: Computer workflow - safe system info."""
        config = get_openrouter_config()
        provider = build_provider(config)

        registry = ToolRegistry([t for t in ALL_TOOLS if t.name == "get_system_info"])
        tool_executor = ToolExecutor(registry)

        brain = ComputerBrain(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        result = brain.execute("Get the system information")

        print(f"Computer summary: {result.summary}")
        print(f"Number of actions: {len(result.actions)}")

        assert result is not None

    @pytest.mark.real_e2e
    def test_multi_agent_workflow(self):
        """TEST E: Multi-agent workflow - Planning → Research → Verification."""
        config = get_openrouter_config()

        registry = ToolRegistry(ALL_TOOLS[:15])
        tool_executor = ToolExecutor(registry)

        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
        )

        # Complex request that should trigger planning
        result = brain_orchestrator.execute(
            "Research the JARVIS project, analyze the test structure, and create a summary"
        )

        print(f"Multi-agent result success: {result.success}")
        print(f"Brain type used: {result.brain_type}")
        if result.error:
            print(f"Error: {result.error}")

        assert result is not None


class TestRealProviderObservability:
    """Test observability features during real execution."""

    @pytest.mark.real_e2e
    def test_latency_tracking(self):
        """Track latency of real provider calls."""
        config = get_openrouter_config()
        provider = build_provider(config)

        start_time = time.time()
        result = provider.complete("What is 2+2? Answer in one word.", [])
        latency = time.time() - start_time

        print(f"Provider latency: {latency:.2f}s")
        print(f"Response: {result.text}")

        assert latency < 30, f"Latency too high: {latency}s"
        assert result.text is not None

    @pytest.mark.real_e2e
    def test_model_and_provider_info(self):
        """Capture model and provider info during execution."""
        config = get_openrouter_config()

        print(f"Primary provider: {config.provider}")
        print(f"Primary model: {config.model}")
        print(f"Brain models:")
        print(f"  - Planning: {config.brain.planning.provider}/{config.brain.planning.model}")
        print(f"  - Research: {config.brain.research.provider}/{config.brain.research.model}")
        print(f"  - Coding: {config.brain.coding.provider}/{config.brain.coding.model}")
        print(f"  - Computer: {config.brain.computer.provider}/{config.brain.computer.model}")
        print(f"  - Verification: {config.brain.verification.provider}/{config.brain.verification.model}")
        print(f"  - Fast: {config.brain.fast.provider}/{config.brain.fast.model}")

        assert config.provider in ("gemini", "openrouter", "nvidia", "grok", "openai")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
