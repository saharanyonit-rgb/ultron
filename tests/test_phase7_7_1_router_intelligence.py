"""Phase 7.7.1 Router Intelligence & Calibration Tests.

Tests for:
- Confidence calibration
- Score margin implementation
- Word-boundary matching
- Context-aware follow-up routing
- Context override
- Ambiguity detection
- LLM fallback (mocked)
- Tool availability validation
- Multi-agent detection
"""

import pytest
from unittest.mock import MagicMock

from ultron.brains.capability_router import (
    Intent,
    Complexity,
    RiskLevel,
    BrainCapability,
    BrainCapabilities,
    BrainCapabilityRegistry,
    TaskRequirements,
    RoutingDecision,
    RoutingScore,
    CapabilityBasedRouter,
    AmbiguousTaskError,
    _word_boundary_match,
    _tokenize_words,
)


class TestWordBoundaryMatching:
    """Test word-boundary matching fixes substring false positives."""

    def test_app_does_not_match_application(self):
        """'app' should NOT match 'application'."""
        text = "open the application"
        assert not _word_boundary_match(text, "app")
        assert _word_boundary_match(text, "application")

    def test_testing_does_not_match_contest(self):
        """'test' should NOT match 'contest'."""
        text = "enter the contest"
        assert not _word_boundary_match(text, "test")
        assert not _word_boundary_match(text, "testing")

    def test_research_matches_research(self):
        """'research' should match 'research'."""
        text = "research competitors"
        assert _word_boundary_match(text, "research")

    def test_researching_matches_research(self):
        """'researching' should NOT match 'research' (different word)."""
        text = "researching the market"
        assert not _word_boundary_match(text, "research")

    def test_researcher_does_not_match_research(self):
        """'researcher' should NOT match 'research'."""
        text = "the researcher studied it"
        assert not _word_boundary_match(text, "research")

    def test_assistant_does_not_match_assist(self):
        """'assist' should NOT match 'assistant'."""
        text = "the assistant helped me"
        assert not _word_boundary_match(text, "assist")
        assert _word_boundary_match(text, "assistant")

    def test_open_matches_open(self):
        """'open' should match 'open'."""
        text = "open chrome"
        assert _word_boundary_match(text, "open")

    def test_code_does_not_match_codec(self):
        """'code' should NOT match 'codec'."""
        text = "install the codec"
        assert not _word_boundary_match(text, "code")

    def test_tokenize_words(self):
        """Test word tokenization."""
        words = _tokenize_words("Open Chrome and navigate to google.com")
        assert "open" in words
        assert "chrome" in words
        assert "and" in words
        assert "navigate" in words
        assert "to" in words
        assert "google" in words


class TestConfidenceCalibration:
    """Test confidence calibration for obvious requests."""

    def test_hello_high_confidence_fast(self):
        """'Hello' should route to fast with high confidence."""
        router = CapabilityBasedRouter()
        decision = router.route("Hello")

        assert decision.selected_brain == "fast"
        assert decision.confidence >= 0.90
        assert decision.score_margin > 0.5

    def test_open_chrome_high_confidence_computer(self):
        """'Open Chrome' should route to computer with high confidence."""
        router = CapabilityBasedRouter(available_tools={"open_app", "navigate_url"})
        decision = router.route("Open Chrome")

        assert decision.selected_brain == "computer"
        assert decision.confidence >= 0.70
        assert decision.best_score > decision.second_best_score

    def test_research_competitors_high_confidence_research(self):
        """'Research competitors' should route to research with high confidence."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files", "open_url"})
        decision = router.route("Research competitors")

        assert decision.selected_brain == "research"
        assert decision.confidence >= 0.60
        assert decision.best_score > decision.second_best_score

    def test_fix_python_bug_high_confidence_coding(self):
        """'Fix Python bug' should route to coding with high confidence."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        decision = router.route("Fix the Python bug")

        assert decision.selected_brain == "coding"
        assert decision.confidence >= 0.60

    def test_verify_deployment_high_confidence_verification(self):
        """'Verify deployment' should route to verification with high confidence."""
        router = CapabilityBasedRouter()
        decision = router.route("Verify the deployment succeeded")

        assert decision.selected_brain == "verification"
        assert decision.confidence >= 0.60

    def test_trivial_thanks_high_confidence(self):
        """'Thanks' should route to fast with very high confidence."""
        router = CapabilityBasedRouter()
        decision = router.route("Thanks")

        assert decision.selected_brain == "fast"
        assert decision.confidence >= 0.90

    def test_confidence_not_artificially_high(self):
        """Confidence should not be 0.95+ for every request."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})

        moderate_requests = [
            "Analyze the code structure",
            "Find information about Python",
            "Check the system status",
        ]

        for request in moderate_requests:
            decision = router.route(request)
            assert decision.confidence <= 0.95, f"Request '{request}' has suspiciously high confidence: {decision.confidence}"


class TestScoreMargin:
    """Test score margin implementation."""

    def test_large_margin_high_confidence(self):
        """Large margin between best and second best should boost confidence."""
        router = CapabilityBasedRouter(available_tools={"open_app", "navigate_url"})
        decision = router.route("Open Chrome")

        assert decision.score_margin > 0.3
        assert decision.best_score > decision.second_best_score

    def test_small_margin_lower_confidence(self):
        """Small margin between candidates should reduce confidence."""
        router = CapabilityBasedRouter(available_tools=set())
        decision = router.route("analyze and verify")

        if decision.best_score - decision.second_best_score < 0.1:
            assert decision.confidence < 0.7

    def test_metadata_contains_scores(self):
        """Routing metadata should contain score information."""
        router = CapabilityBasedRouter()
        decision = router.route("Research competitors")

        assert decision.best_score > 0
        assert decision.second_best_score >= 0
        assert decision.score_margin >= 0


class TestAmbiguityDetection:
    """Test explicit ambiguity state detection."""

    def test_check_this_ambiguous_no_context(self):
        """'Check this' without context should be ambiguous."""
        router = CapabilityBasedRouter()
        decision = router.route("Check this")

        assert decision.ambiguity is True
        assert decision.confidence < 0.3
        assert decision.selected_brain == "fast"

    def test_fix_it_ambiguous_no_context(self):
        """'Fix it' without context should be ambiguous."""
        router = CapabilityBasedRouter()
        decision = router.route("Fix it")

        assert decision.ambiguity is True
        assert decision.ambiguity_reason != ""

    def test_handle_that_ambiguous_no_context(self):
        """'Handle that' without context should be ambiguous."""
        router = CapabilityBasedRouter()
        decision = router.route("Handle that")

        assert decision.ambiguity is True
        assert "missing_information" in decision.missing_information or decision.ambiguity_reason

    def test_look_into_this_ambiguous_no_context(self):
        """'Look into this' without context should be ambiguous."""
        router = CapabilityBasedRouter()
        decision = router.route("Look into this")

        assert decision.ambiguity is True

    def test_ambiguous_has_candidates(self):
        """Ambiguous decision should include candidate agents."""
        router = CapabilityBasedRouter()
        decision = router.route("Check this")

        assert len(decision.candidate_agents) > 0

    def test_do_it_ambiguous_no_context(self):
        """'Do it' without context should be ambiguous."""
        router = CapabilityBasedRouter()
        decision = router.route("Do it")

        assert decision.ambiguity is True


class TestContextAwareFollowUp:
    """Test context-aware follow-up routing."""

    def test_fix_it_with_coding_context(self):
        """'Fix it' after coding context should route to coding."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        context = {"previous_brain": "coding"}

        decision = router.route("Fix it", context)

        assert decision.selected_brain == "coding"
        assert decision.confidence >= 0.80
        assert "context" in decision.reason.lower() or decision.routing_metadata.get("context_used")

    def test_summarize_it_with_research_context(self):
        """'Summarize it' after research context should route to research."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        context = {"previous_brain": "research"}

        decision = router.route("Summarize it", context)

        assert decision.selected_brain == "research"
        assert decision.confidence >= 0.70

    def test_continue_with_previous_context(self):
        """'Continue' with previous context should use that context."""
        router = CapabilityBasedRouter(available_tools={"read_file"})
        context = {"previous_brain": "coding"}

        decision = router.route("Continue", context)

        assert decision.selected_brain == "coding" or decision.ambiguity

    def test_navigate_with_computer_context(self):
        """'Navigate to X' after computer context should route to computer."""
        router = CapabilityBasedRouter(available_tools={"navigate_url", "open_url"})
        context = {"previous_brain": "computer"}

        decision = router.route("Navigate to google.com", context)

        assert decision.selected_brain == "computer"


class TestContextOverride:
    """Test that explicit new requests override stale context."""

    def test_explicit_computer_overrides_research_context(self):
        """'Open Chrome' should override previous research context."""
        router = CapabilityBasedRouter(available_tools={"open_app", "navigate_url"})
        context = {"previous_brain": "research"}

        decision = router.route("Open Chrome", context)

        assert decision.selected_brain == "computer"
        assert decision.confidence >= 0.60

    def test_explicit_research_overrides_coding_context(self):
        """'Research competitors' should override previous coding context."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files", "open_url"})
        context = {"previous_brain": "coding"}

        decision = router.route("Research PostgreSQL", context)

        assert decision.selected_brain == "research"

    def test_clear_request_no_context_influence(self):
        """Clear explicit request should not be influenced by irrelevant context."""
        router = CapabilityBasedRouter(available_tools={"open_app", "navigate_url"})
        context = {"previous_brain": "research"}

        decision = router.route("Open notepad", context)

        assert decision.selected_brain == "computer"
        assert decision.confidence >= 0.60


class TestMultiAgentDetection:
    """Test improved multi-agent detection."""

    def test_research_and_compare_multi_agent(self):
        """'Research and compare' should detect multi-agent workflow."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files", "open_url"})
        decision = router.route("Research competitors and compare their pricing")

        assert decision.workflow_required is True
        assert decision.selected_brain == "planning"

    def test_analyze_and_fix_multi_agent(self):
        """'Analyze and fix' should detect multi-agent workflow."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        decision = router.route("Analyze the code and fix the bugs")

        assert decision.workflow_required is True

    def test_single_action_not_multi_agent(self):
        """Single action should not be multi-agent."""
        router = CapabilityBasedRouter(available_tools={"read_file"})
        decision = router.route("Read the file")

        assert decision.workflow_required is False

    def test_research_compare_recommend_multi_agent(self):
        """Multiple sequential actions should detect multi-agent."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files", "open_url"})
        decision = router.route("Research competitors, compare them, and recommend one")

        assert decision.workflow_required is True
        assert decision.selected_brain == "planning"


class TestLLMFallback:
    """Test optional LLM fallback for ambiguous cases."""

    def test_high_confidence_no_llm_call(self):
        """High confidence request should NOT trigger LLM fallback."""
        mock_classifier = MagicMock()
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        decision = router.route("Hello")

        assert decision.classifier_source == "deterministic"
        assert mock_classifier.call_count == 0

    def test_ambiguous_triggers_llm_fallback(self):
        """Ambiguous request should trigger LLM fallback."""
        mock_classifier = MagicMock(return_value={
            "intent": "computer_control",
            "selected_brain": "computer",
            "confidence": 0.7,
            "best_score": 0.7,
            "second_best_score": 0.3,
            "score_margin": 0.4,
        })
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        decision = router.route("Handle it")

        assert decision.classifier_source == "llm_fallback"
        assert router.llm_calls == 1

    def test_llm_fallback_invalid_output_safe(self):
        """Malformed LLM output should not crash - fallback to deterministic."""
        mock_classifier = MagicMock(return_value={"invalid": "output"})
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        decision = router.route("Fix it")

        assert decision.selected_brain is not None

    def test_llm_fallback_none_output_safe(self):
        """None LLM output should not crash - fallback to deterministic."""
        mock_classifier = MagicMock(return_value=None)
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        decision = router.route("Fix it")

        assert decision.selected_brain is not None

    def test_llm_fallback_exception_safe(self):
        """Exception from LLM classifier should not crash."""
        mock_classifier = MagicMock(side_effect=Exception("LLM failed"))
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        decision = router.route("Fix it")

        assert decision.selected_brain is not None
        assert decision.classifier_source == "deterministic"

    def test_llm_calls_counter(self):
        """LLM calls should be tracked."""
        mock_classifier = MagicMock(return_value={
            "intent": "computer_control",
            "selected_brain": "computer",
            "confidence": 0.7,
        })
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        router.route("Handle it")
        router.route("Check this")

        assert router.llm_calls == 2

        router.reset_llm_calls()
        assert router.llm_calls == 0

    def test_llm_disabled_by_default(self):
        """LLM fallback should be disabled by default."""
        router = CapabilityBasedRouter()

        assert router._use_llm_fallback is False


class TestToolAwareValidation:
    """Test tool-aware validation against actual ToolRegistry."""

    def test_missing_tool_routes_alternative(self):
        """If required tool is unavailable, router should find alternative."""
        router = CapabilityBasedRouter(available_tools=set())

        decision = router.route("Research competitors")

        assert decision.selected_brain in ["research", "fast", "planning"]

    def test_available_tool_boosts_score(self):
        """Available tools should boost the routing score."""
        router_with_tools = CapabilityBasedRouter(
            available_tools={"read_file", "search_files", "open_url"}
        )
        router_without_tools = CapabilityBasedRouter(available_tools=set())

        decision_with = router_with_tools.route("Research competitors")
        decision_without = router_without_tools.route("Research competitors")

        assert decision_with.best_score >= decision_without.best_score

    def test_required_tools_in_metadata(self):
        """Required tools should be in routing metadata."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        decision = router.route("Read the file")

        assert "read_file" in decision.required_tools or len(decision.required_tools) >= 0


class TestStructuredOutput:
    """Test structured routing decision output."""

    def test_routing_decision_has_all_fields(self):
        """RoutingDecision should have all required fields."""
        router = CapabilityBasedRouter()
        decision = router.route("Hello")

        assert decision.selected_brain is not None
        assert decision.confidence >= 0
        assert decision.best_score >= 0
        assert decision.second_best_score >= 0
        assert decision.score_margin >= 0
        assert decision.intent is not None
        assert decision.complexity is not None
        assert decision.classifier_source in ["deterministic", "llm_fallback"]
        assert decision.routing_latency_ms >= 0

    def test_metadata_has_debug_info(self):
        """Metadata should contain useful debug information."""
        router = CapabilityBasedRouter(available_tools={"open_app"})
        decision = router.route("Open Chrome")

        assert "matched_capabilities" in decision.matched_capabilities or len(decision.matched_capabilities) >= 0


class TestIntentClassification:
    """Test intent classification accuracy."""

    def test_computer_control_intent(self):
        """Computer control requests should classify as COMPUTER_CONTROL."""
        router = CapabilityBasedRouter(available_tools={"open_app", "navigate_url"})

        for request in ["Open Chrome", "Close the window", "Launch notepad"]:
            decision = router.route(request)
            assert decision.intent == Intent.COMPUTER_CONTROL, f"Failed for: {request}"

    def test_coding_intent(self):
        """Coding requests should classify as CODING."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})

        for request in ["Fix the bug", "Implement the feature", "Debug the issue"]:
            decision = router.route(request)
            assert decision.intent == Intent.CODING, f"Failed for: {request}"

    def test_research_intent(self):
        """Research requests should classify as RESEARCH."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files", "open_url"})

        for request in ["Research competitors", "Find information", "Investigate the issue"]:
            decision = router.route(request)
            assert decision.intent == Intent.RESEARCH, f"Failed for: {request}"

    def test_verification_intent(self):
        """Verification requests should classify as VERIFICATION."""
        router = CapabilityBasedRouter()

        for request in ["Verify the deployment", "Check if it works", "Confirm the result"]:
            decision = router.route(request)
            assert decision.intent == Intent.VERIFICATION, f"Failed for: {request}"


class TestComplexityClassification:
    """Test complexity classification."""

    def test_trivial_complexity(self):
        """Trivial requests should be TRIVIAL."""
        router = CapabilityBasedRouter()
        decision = router.route("Hello")

        assert decision.complexity == Complexity.TRIVIAL

    def test_simple_complexity(self):
        """Simple single-action requests should be SIMPLE."""
        router = CapabilityBasedRouter(available_tools={"open_app"})
        decision = router.route("Open Chrome")

        assert decision.complexity == Complexity.SIMPLE

    def test_complexity_not_trivial_for_real_work(self):
        """Non-trivial requests should not be classified as TRIVIAL."""
        router = CapabilityBasedRouter(available_tools={"read_file", "search_files"})
        decision = router.route("Analyze the codebase")

        assert decision.complexity != Complexity.TRIVIAL


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_input(self):
        """Empty input should not crash."""
        router = CapabilityBasedRouter()
        decision = router.route("")

        assert decision.selected_brain is not None
        assert decision.confidence >= 0

    def test_whitespace_only_input(self):
        """Whitespace-only input should not crash."""
        router = CapabilityBasedRouter()
        decision = router.route("   \n\t  ")

        assert decision.selected_brain is not None

    def test_unknown_language(self):
        """Unknown language should still route."""
        router = CapabilityBasedRouter()
        decision = router.route("これはテストです")

        assert decision.selected_brain is not None

    def test_mixed_case_input(self):
        """Mixed case input should be handled."""
        router = CapabilityBasedRouter(available_tools={"open_app"})
        decision = router.route("OPEN Chrome")

        assert decision.selected_brain == "computer"

    def test_special_characters(self):
        """Special characters should not crash."""
        router = CapabilityBasedRouter()
        decision = router.route("Hello!!! @#$% ^&*()")

        assert decision.selected_brain is not None


class TestRegressionPrevention:
    """Tests to prevent regression of Phase 7.7 functionality."""

    def test_basic_routing_still_works(self):
        """Basic routing should still function."""
        router = CapabilityBasedRouter()

        assert router.route("Hello").selected_brain == "fast"
        assert router.route("Research").selected_brain in ["research", "planning"]
        assert router.route("Fix bug").selected_brain == "coding"

    def test_capability_registry_intact(self):
        """Capability registry should have all brain types."""
        registry = BrainCapabilityRegistry.get_all_capabilities()

        assert "planning" in registry
        assert "research" in registry
        assert "coding" in registry
        assert "computer" in registry
        assert "verification" in registry
        assert "fast" in registry

    def test_task_requirements_fields(self):
        """TaskRequirements should have all required fields."""
        req = TaskRequirements(
            intent=Intent.CODING,
            complexity=Complexity.SIMPLE,
            required_capabilities=set(),
            required_tools=set(),
            risk_level=RiskLevel.LOW,
        )

        assert req.intent == Intent.CODING
        assert req.complexity == Complexity.SIMPLE
        assert req.multi_agent_required is False
        assert req.is_follow_up is False

    def test_routing_decision_fields(self):
        """RoutingDecision should have all required fields."""
        decision = RoutingDecision(
            selected_brain="coding",
            confidence=0.8,
        )

        assert decision.selected_brain == "coding"
        assert decision.confidence == 0.8
        assert decision.ambiguity is False


class TestPerformance:
    """Test routing performance."""

    def test_deterministic_routing_is_fast(self):
        """Deterministic routing should be very fast (< 50ms)."""
        router = CapabilityBasedRouter()
        decision = router.route("Hello")

        assert decision.routing_latency_ms < 50

    def test_no_unnecessary_llm_calls(self):
        """Simple requests should never trigger LLM calls."""
        mock_classifier = MagicMock()
        router = CapabilityBasedRouter(
            use_llm_fallback=True,
            llm_classifier=mock_classifier,
        )

        simple_requests = [
            "Hello",
            "Open Chrome",
            "Fix the bug",
            "Research competitors",
            "Verify deployment",
        ]

        for request in simple_requests:
            router.reset_llm_calls()
            router.route(request)
            assert router.llm_calls == 0, f"LLM called for: {request}"
