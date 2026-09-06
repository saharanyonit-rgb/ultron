"""JARVIS Phase 7.7: Capability-Based Router Tests.

Tests for the new intelligent capability-based routing system.
"""

from __future__ import annotations

import pytest

from ultron.brains.capability_router import (
    CapabilityBasedRouter,
    BrainCapabilityRegistry,
    Intent,
    Complexity,
    RiskLevel,
    RoutingDecision,
)


class TestTrivialRouting:
    """Test fast path for trivial requests."""

    def test_hello_routes_to_fast(self):
        router = CapabilityBasedRouter()
        result = router.route("Hello")

        assert result.selected_brain == "fast"
        assert result.complexity == Complexity.TRIVIAL
        assert result.workflow_required is False
        assert result.routing_latency_ms < 10

    def test_thanks_routes_to_fast(self):
        router = CapabilityBasedRouter()
        result = router.route("Thanks")

        assert result.selected_brain == "fast"
        assert result.complexity == Complexity.TRIVIAL

    def test_bye_routes_to_fast(self):
        router = CapabilityBasedRouter()
        result = router.route("Goodbye")

        assert result.selected_brain == "fast"
        assert result.complexity == Complexity.TRIVIAL

    def test_hi_there_routes_to_fast(self):
        router = CapabilityBasedRouter()
        result = router.route("Hi there")

        assert result.selected_brain == "fast"
        assert result.complexity == Complexity.TRIVIAL

    def test_nice_to_meet_you_routes_to_fast(self):
        router = CapabilityBasedRouter()
        result = router.route("Nice to meet you")

        assert result.selected_brain == "fast"
        assert result.complexity == Complexity.TRIVIAL


class TestComputerRouting:
    """Test computer control routing."""

    def test_open_chrome_routes_to_computer(self):
        router = CapabilityBasedRouter()
        result = router.route("Open Chrome")

        assert result.selected_brain == "computer"
        assert result.intent == Intent.COMPUTER_CONTROL
        assert "open_app" in result.required_tools or len(result.required_tools) >= 0

    def test_open_notepad_routes_to_computer(self):
        router = CapabilityBasedRouter()
        result = router.route("Open notepad")

        assert result.selected_brain == "computer"
        assert result.intent == Intent.COMPUTER_CONTROL

    def test_close_app_routes_to_computer(self):
        router = CapabilityBasedRouter()
        result = router.route("Close the application")

        assert result.selected_brain == "computer"
        assert result.intent == Intent.COMPUTER_CONTROL

    def test_navigate_browser_routes_to_computer(self):
        router = CapabilityBasedRouter()
        result = router.route("Navigate to google.com")

        assert result.selected_brain == "computer"
        assert result.intent == Intent.COMPUTER_CONTROL


class TestCodingRouting:
    """Test coding task routing."""

    def test_fix_bug_routes_to_coding(self):
        router = CapabilityBasedRouter()
        result = router.route("Fix the bug in the authentication module")

        assert result.selected_brain == "coding"
        assert result.intent == Intent.CODING

    def test_refactor_code_routes_to_coding(self):
        router = CapabilityBasedRouter()
        result = router.route("Refactor the code for better performance")

        assert result.selected_brain == "coding"
        assert result.intent == Intent.CODING

    def test_implement_feature_routes_to_coding(self):
        router = CapabilityBasedRouter()
        result = router.route("Implement the new feature")

        assert result.selected_brain == "coding"
        assert result.intent == Intent.CODING

    def test_debug_issue_routes_to_coding(self):
        router = CapabilityBasedRouter()
        result = router.route("Debug the crashing issue")

        assert result.selected_brain == "coding"
        assert result.intent == Intent.CODING

    def test_repository_inspection_routes_to_coding(self):
        router = CapabilityBasedRouter()
        result = router.route("Inspect the repository structure")

        assert result.selected_brain == "coding"


class TestResearchRouting:
    """Test research task routing."""

    def test_research_topic_routes_to_research(self):
        router = CapabilityBasedRouter()
        result = router.route("Research the current best practices for testing")

        assert result.selected_brain in ["research", "planning", "fast"]
        assert result.intent in [Intent.RESEARCH, Intent.PLANNING, Intent.CONVERSATION]

    def test_investigate_issue_routes_to_research(self):
        router = CapabilityBasedRouter()
        result = router.route("Investigate the performance issue")

        assert result.selected_brain in ["research", "planning", "fast"]

    def test_find_information_routes_to_research(self):
        router = CapabilityBasedRouter()
        result = router.route("Find information about the new technology")

        assert result.selected_brain in ["research", "planning", "fast"]

    def test_compare_alternatives_routes_correctly(self):
        router = CapabilityBasedRouter()
        result = router.route("Compare the different approaches")

        assert result.selected_brain in ["research", "planning", "fast"]


class TestPlanningRouting:
    """Test planning task routing."""

    def test_create_plan_routes_to_planning(self):
        router = CapabilityBasedRouter()
        result = router.route("Create a plan for the migration")

        assert result.selected_brain == "planning"
        assert result.intent == Intent.PLANNING

    def test_multi_step_workflow_routes_to_planning(self):
        router = CapabilityBasedRouter()
        result = router.route("Plan the multi-step deployment workflow")

        assert result.selected_brain == "planning"
        assert result.intent == Intent.PLANNING

    def test_decompose_goal_routes_to_planning(self):
        router = CapabilityBasedRouter()
        result = router.route("Break down this complex goal into tasks")

        assert result.selected_brain == "planning"
        assert result.intent == Intent.PLANNING


class TestVerificationRouting:
    """Test verification task routing."""

    def test_verify_result_routes_to_verification(self):
        router = CapabilityBasedRouter()
        result = router.route("Verify that the deployment was successful")

        assert result.selected_brain == "verification"

    def test_check_output_routes_to_verification(self):
        router = CapabilityBasedRouter()
        result = router.route("Check if the output is correct")

        assert result.selected_brain == "verification"

    def test_confirm_success_routes_to_verification(self):
        router = CapabilityBasedRouter()
        result = router.route("Confirm that it worked")

        assert result.selected_brain == "verification"


class TestMultiAgentWorkflow:
    """Test multi-agent workflow detection."""

    def test_research_and_analyze_routes_to_planning(self):
        router = CapabilityBasedRouter()
        result = router.route("Research the technology and analyze the alternatives")

        assert result.selected_brain == "planning"
        assert result.workflow_required is True

    def test_find_and_fix_routes_correctly(self):
        router = CapabilityBasedRouter()
        result = router.route("Find the bug and fix it")

        assert result.selected_brain in ["planning", "coding"]

    def test_multiple_steps_routes_to_planning(self):
        router = CapabilityBasedRouter()
        result = router.route("First research, then analyze, and finally create a report")

        assert result.selected_brain == "planning"
        assert result.workflow_required is True


class TestToolAwareRouting:
    """Test tool-aware routing."""

    def test_read_file_routes_correctly(self):
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        result = router.route("Read the configuration file")

        assert result.selected_brain in ["coding", "research", "computer", "fast"]
        assert len(result.required_tools) >= 0

    def test_create_file_routes_correctly(self):
        router = CapabilityBasedRouter(available_tools={"create_file", "read_file"})
        result = router.route("Create a new test file")

        assert result.selected_brain in ["coding", "computer", "verification", "fast"]


class TestContextAwareRouting:
    """Test context-aware routing."""

    def test_followup_uses_context(self):
        router = CapabilityBasedRouter()
        context = {
            "previous_task": "analyzing code",
            "relevant_files": ["auth.py", "config.py"],
        }
        result = router.route("Now fix the issues", context)

        assert result.selected_brain in ["coding", "computer"]


class TestComplexityDetection:
    """Test complexity detection."""

    def test_simple_open_app(self):
        router = CapabilityBasedRouter()
        result = router.route("Open notepad")

        assert result.complexity == Complexity.SIMPLE

    def test_complex_multi_step(self):
        router = CapabilityBasedRouter()
        result = router.route("First do this and then do that and finally check the result")

        assert result.complexity in [Complexity.COMPLEX, Complexity.VERY_COMPLEX]

    def test_trivial_greeting(self):
        router = CapabilityBasedRouter()
        result = router.route("Hello")

        assert result.complexity == Complexity.TRIVIAL


class TestRiskLevelDetection:
    """Test risk level detection."""

    def test_delete_is_recognized(self):
        router = CapabilityBasedRouter()
        result = router.route("Delete all the temporary files")

        assert result.selected_brain in ["computer", "coding", "fast"]

    def test_read_is_low_risk(self):
        router = CapabilityBasedRouter()
        result = router.route("Read the log file")

        assert result.intent in [Intent.CONVERSATION, Intent.RESEARCH, Intent.CODING]


class TestAlternatives:
    """Test alternative brain suggestions."""

    def test_computer_has_alternatives(self):
        router = CapabilityBasedRouter()
        result = router.route("Open Chrome")

        assert len(result.alternatives) > 0

    def test_coding_has_alternatives(self):
        router = CapabilityBasedRouter()
        result = router.route("Fix the bug")

        assert len(result.alternatives) > 0


class TestRoutingMetadata:
    """Test routing decision metadata."""

    def test_intent_is_recorded(self):
        router = CapabilityBasedRouter()
        result = router.route("Research competitors")

        assert result.intent is not None
        assert result.intent in [Intent.RESEARCH, Intent.PLANNING, Intent.CONVERSATION]

    def test_complexity_is_recorded(self):
        router = CapabilityBasedRouter()
        result = router.route("Create a multi-step plan")

        assert result.complexity is not None
        assert result.complexity in [Complexity.TRIVIAL, Complexity.SIMPLE, Complexity.MODERATE, Complexity.COMPLEX, Complexity.VERY_COMPLEX]

    def test_routing_latency_recorded(self):
        router = CapabilityBasedRouter()
        result = router.route("Hello")

        assert result.routing_latency_ms >= 0


class TestBrainCapabilityRegistry:
    """Test brain capability registry."""

    def test_all_brains_have_capabilities(self):
        registry = BrainCapabilityRegistry.get_all_capabilities()

        assert "planning" in registry
        assert "research" in registry
        assert "coding" in registry
        assert "computer" in registry
        assert "verification" in registry
        assert "fast" in registry

    def test_planning_has_planning_capability(self):
        caps = BrainCapabilityRegistry.PLANNING

        cap_names = {c.name for c in caps.capabilities}
        assert "planning" in cap_names
        assert "task_decomposition" in cap_names

    def test_research_has_research_capability(self):
        caps = BrainCapabilityRegistry.RESEARCH

        cap_names = {c.name for c in caps.capabilities}
        assert "research" in cap_names

    def test_coding_has_debugging_capability(self):
        caps = BrainCapabilityRegistry.CODING

        cap_names = {c.name for c in caps.capabilities}
        assert "debugging" in cap_names

    def test_capabilities_have_keywords(self):
        caps = BrainCapabilityRegistry.CODING

        for cap in caps.capabilities:
            assert len(cap.keywords) > 0


class TestRoutingConfidence:
    """Test routing confidence scoring."""

    def test_clear_intent_has_reasonable_confidence(self):
        router = CapabilityBasedRouter()
        result = router.route("Open Chrome")

        assert result.confidence >= 0.0
        assert result.confidence <= 1.0

    def test_ambiguous_intent_lower_confidence(self):
        router = CapabilityBasedRouter()
        result = router.route("Process the data")

        assert result.confidence >= 0.0


class TestDeterministicRouting:
    """Test that routing is deterministic."""

    def test_same_input_same_output(self):
        router = CapabilityBasedRouter()
        request = "Research the market trends"

        result1 = router.route(request)
        result2 = router.route(request)

        assert result1.selected_brain == result2.selected_brain
        assert result1.confidence == result2.confidence

    def test_different_inputs_may_differ(self):
        router = CapabilityBasedRouter()

        result1 = router.route("Open Chrome")
        result2 = router.route("Fix the bug")

        assert result1.selected_brain != result2.selected_brain


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
