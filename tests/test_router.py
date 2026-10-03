"""Unit tests for the JARVIS Intent Router (`ultron.core.router`)."""

from __future__ import annotations

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.core.agent import Agent
from ultron.core.brain import Brain, ResponseStatus
from ultron.core.router import IntentRouter, RouteType
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.risk import RiskLevel
from ultron.tools import ALL_TOOLS, ToolRegistry
from ultron.tools.base import Tool


class ScriptedLLMProvider(LLMProvider):
    name = "scripted_router_provider"

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses) if responses else []
        self.should_fail = False

    def complete(self, text: str | None, tools) -> ProviderResult:
        if self.should_fail:
            raise RuntimeError("LLM Service Unavailable")
        if not self._responses:
            return ProviderResult(text="CONVERSATIONAL||0.8|General query", tool_calls=[])
        return ProviderResult(text=self._responses.pop(0), tool_calls=[])

    def feed_tool_results(self, results) -> None:
        pass


class SpyTool(Tool):
    name = "spy_tool"
    description = "Spy tool for testing execution isolation."
    parameters = {"type": "object", "properties": {}}
    output_schema = {"type": "object", "properties": {}}
    # Required: the catalog refuses to register an unclassified tool, because an
    # unclassified tool is a security hole rather than a safe default.
    risk = RiskLevel.READ

    def __init__(self) -> None:
        self.was_executed = False

    def run(self, **kwargs):
        self.was_executed = True
        return {"executed": True}


# --- Test 1: Simple conversational request ---
def test_simple_conversational_request():
    router = IntentRouter(tools=ALL_TOOLS)
    decision = router.route("What is the speed of light?")

    assert decision.route_type == RouteType.CONVERSATIONAL
    assert decision.confidence > 0.5


# --- Test 2: Known tool request ---
def test_known_tool_request():
    router = IntentRouter(tools=ALL_TOOLS)
    decision = router.route("get my system info")

    assert decision.route_type == RouteType.TOOL
    assert decision.target == "get_system_info"
    assert decision.confidence >= 0.9


# --- Test 3: Known agent request ---
def test_known_agent_request():
    router = IntentRouter(tools=ALL_TOOLS)
    decision = router.route("first read file text.txt and then create file copy.txt")

    assert decision.route_type == RouteType.AGENT
    assert decision.confidence >= 0.8


# --- Test 4: Capability with a registered tool is routable, not "unsupported" ---
def test_registered_capability_is_not_unsupported():
    """Mouse control used to be hard-coded as UNSUPPORTED.

    It is a registered tool, so the router refusing it was a self-contradiction:
    the router claimed no such capability existed while `mouse_move` sat in the
    registry. Routing now derives from tool metadata, so this must reach the tool.
    """
    router = IntentRouter(tools=ALL_TOOLS)
    decision = router.route("move mouse cursor to coordinates 100, 200")

    assert decision.route_type == RouteType.AGENT
    assert decision.target == "mouse_move"


# --- Test 4b: A genuinely absent capability is refused ---
def test_genuinely_unsupported_capability():
    router = IntentRouter(tools=ALL_TOOLS)
    decision = router.route("fine-tune ollama on my dataset")

    assert decision.route_type == RouteType.UNSUPPORTED
    assert decision.confidence == 1.0


# --- Test 4c: Routing never contradicts the registry ---
def test_no_unsupported_pattern_is_actually_implemented():
    """validate_out_of_scope raises if an out-of-scope entry has a tool."""
    from ultron.core.router import validate_out_of_scope
    from ultron.tools.catalog import default_catalog

    validate_out_of_scope(default_catalog())


# --- Test 5: Empty/invalid request ---
def test_empty_invalid_request():
    router = IntentRouter(tools=ALL_TOOLS)

    for invalid in ("", "   ", None):
        decision = router.route(invalid)
        assert decision.route_type == RouteType.CONVERSATIONAL
        assert decision.confidence == 0.0


# --- Test 6: LLM classification failure ---
def test_llm_classification_failure():
    provider = ScriptedLLMProvider()
    provider.should_fail = True
    router = IntentRouter(tools=[], provider=provider, use_llm_classification=True)

    decision = router.route("Explain quantum physics")
    assert decision.route_type == RouteType.CONVERSATIONAL
    assert "failure" in decision.reasoning.lower()


# --- Test 7: Low-confidence classification/fallback ---
def test_low_confidence_classification_fallback():
    # Response format: CATEGORY|TARGET|CONFIDENCE|REASON
    provider = ScriptedLLMProvider(["AGENT|agent_loop|0.2|Uncertain classification"])
    router = IntentRouter(tools=[], provider=provider, min_confidence=0.6, use_llm_classification=True)

    decision = router.route("Tell me a story about space")
    assert decision.route_type == RouteType.CONVERSATIONAL
    assert decision.confidence == 0.2
    assert "fallback" in decision.reasoning.lower()


# --- Test 8: Invalid routing result ---
def test_invalid_routing_result():
    provider = ScriptedLLMProvider(["GIBBERISH_CATEGORY|target|0.9|reason"])
    router = IntentRouter(tools=[], provider=provider, use_llm_classification=True)

    decision = router.route("Help me write an essay")
    assert decision.route_type == RouteType.CONVERSATIONAL


# --- Test 9: Router does not execute tools itself ---
def test_router_does_not_execute_tools():
    spy = SpyTool()
    router = IntentRouter(tools=[spy])

    decision = router.route("run spy tool")
    assert decision.route_type in (RouteType.TOOL, RouteType.AGENT, RouteType.CONVERSATIONAL)
    # The router MUST NOT execute the tool
    assert spy.was_executed is False


# --- Test 10: Brain integration with Router ---
def test_brain_integration_with_router(tmp_path):
    provider = ScriptedLLMProvider(["CONVERSATIONAL||0.9|General query"])
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
    )
    brain = Brain(agent=agent)

    # Test unsupported route through Brain. Mouse control is registered, so the
    # unsupported path is exercised with a capability that genuinely has no tool.
    resp = brain.process("fine-tune ollama on my dataset")
    assert resp.status == ResponseStatus.SUCCESS
    assert "cannot perform this action" in resp.response.lower()
    assert resp.metadata.get("route") == "unsupported"
