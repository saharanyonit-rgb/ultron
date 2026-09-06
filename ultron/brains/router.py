"""Agent Router for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

Selects the appropriate specialized brain based on:
- Goal/task type
- Required capabilities
- Complexity
- Context

The router does NOT execute tools - it only selects the agent.

Phase 7.7: Enhanced with capability-based routing that uses structured
capability models instead of primarily keyword-based matching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability
from ultron.core.router import IntentRouter, RouteDecision, RouteType

logger = logging.getLogger("ultron.brains.router")


class BrainType(str, Enum):
    PLANNING = "planning"
    RESEARCH = "research"
    CODING = "coding"
    COMPUTER = "computer"
    VERIFICATION = "verification"
    FAST = "fast"
    GENERAL = "general"


@dataclass
class BrainRouteDecision:
    """Routing decision for specialized brain selection."""

    brain_type: BrainType
    confidence: float = 1.0
    reasoning: str = ""
    required_capabilities: List[AgentCapability] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    routing_decision: Any = None


class BrainRouter:
    """Routes requests to the appropriate specialized brain.

    The router analyzes the user request and determines which brain
    should handle it based on:
    - Intent classification
    - Capability requirements
    - Complexity indicators
    - Domain-specific keywords

    Phase 7.7: Now uses CapabilityBasedRouter for intelligent routing
    with structured capability models.
    """

    PLANNING_KEYWORDS = {
        "plan", "strategy", "execute", "step", "steps", "workflow",
        "multiple", "sequence", "coordinate", "decompose", "break down",
        "subtask", "parallel", "dependency", "roadmap", "milestone",
    }

    RESEARCH_KEYWORDS = {
        "research", "search", "find", "look up", "investigate", "explore",
        "analyze", "compare", "evaluate", "review", "survey", "study",
        "information", "facts", "sources", "competitor", "pricing",
    }

    CODING_KEYWORDS = {
        "code", "programming", "implement", "bug", "fix", "error",
        "function", "class", "module", "refactor", "test", "debug",
        "repository", "file", "commit", "repository", "git", "merge",
        "authentication", "login", "feature", "development",
    }

    COMPUTER_KEYWORDS = {
        "open", "close", "click", "type", "browse", "navigate",
        "mouse", "keyboard", "screen", "window", "application",
        "chrome", "browser", "app", "desktop", "launch",
    }

    VERIFICATION_KEYWORDS = {
        "verify", "check", "confirm", "validate", "test", "ensure",
        "inspect", "review", "success", "failed", "result", "output",
        "did it work", "was it successful", "confirm that",
    }

    def __init__(
        self,
        intent_router: Optional[IntentRouter] = None,
        use_capability_routing: bool = True,
        available_tools: Optional[set] = None,
        use_llm_fallback: bool = False,
        confidence_threshold: float = 0.35,
        llm_classifier: Optional[Any] = None,
    ) -> None:
        self._intent_router = intent_router or IntentRouter()
        self._use_capability_routing = use_capability_routing
        self._capability_router = None
        self._available_tools = available_tools or set()

        import os as _os
        _use_llm = use_llm_fallback
        if _os.environ.get("JARVIS_ROUTER_LLM_FALLBACK", "").lower() == "true":
            _use_llm = True

        _threshold = float(_os.environ.get("JARVIS_ROUTER_CONFIDENCE_THRESHOLD", str(confidence_threshold)))

        if self._use_capability_routing:
            from ultron.brains.capability_router import CapabilityBasedRouter
            self._capability_router = CapabilityBasedRouter(
                available_tools=self._available_tools,
                use_llm_fallback=_use_llm,
                confidence_threshold=_threshold,
                llm_classifier=llm_classifier,
            )

    def route(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> BrainRouteDecision:
        """Analyze user input and select the appropriate brain.

        Args:
            user_input: The user's request
            context: Optional context with task details

        Returns:
            BrainRouteDecision with the selected brain and reasoning
        """
        if self._capability_router:
            return self._route_with_capabilities(user_input, context)

        return self._route_legacy(user_input, context)

    def _route_with_capabilities(self, user_input: str, context: Optional[Dict[str, Any]]) -> BrainRouteDecision:
        """Route using the new capability-based router."""
        routing_decision = self._capability_router.route(user_input, context)

        brain_type_map = {
            "planning": BrainType.PLANNING,
            "research": BrainType.RESEARCH,
            "coding": BrainType.CODING,
            "computer": BrainType.COMPUTER,
            "verification": BrainType.VERIFICATION,
            "fast": BrainType.FAST,
        }

        brain_type = brain_type_map.get(
            routing_decision.selected_brain,
            BrainType.FAST
        )

        capability_map = {
            BrainType.PLANNING: [AgentCapability.TASK],
            BrainType.RESEARCH: [AgentCapability.RESEARCH],
            BrainType.CODING: [AgentCapability.CODING],
            BrainType.COMPUTER: [AgentCapability.GENERAL],
            BrainType.VERIFICATION: [AgentCapability.GENERAL],
            BrainType.FAST: [AgentCapability.GENERAL],
        }

        return BrainRouteDecision(
            brain_type=brain_type,
            confidence=routing_decision.confidence,
            reasoning=routing_decision.reason,
            required_capabilities=capability_map.get(brain_type, [AgentCapability.GENERAL]),
            metadata={
                "intent": routing_decision.intent.value if routing_decision.intent else "unknown",
                "complexity": routing_decision.complexity.value if routing_decision.complexity else "unknown",
                "matched_capabilities": routing_decision.matched_capabilities,
                "required_tools": routing_decision.required_tools,
                "workflow_required": routing_decision.workflow_required,
                "alternatives": routing_decision.alternatives,
                "routing_latency_ms": routing_decision.routing_latency_ms,
                "best_score": routing_decision.best_score,
                "second_best_score": routing_decision.second_best_score,
                "score_margin": routing_decision.score_margin,
                "ambiguity": routing_decision.ambiguity,
                "ambiguity_reason": routing_decision.ambiguity_reason,
                "missing_information": routing_decision.missing_information,
                "candidate_agents": routing_decision.candidate_agents,
                "needs_llm_classification": routing_decision.needs_llm_classification,
                "classifier_source": routing_decision.classifier_source,
            },
            routing_decision=routing_decision,
        )

    def _route_legacy(self, user_input: str, context: Optional[Dict[str, Any]]) -> BrainRouteDecision:
        """Legacy keyword-based routing for backwards compatibility."""
        text = user_input.lower().strip()

        intent_decision = self._intent_router.route(user_input)

        if intent_decision.route_type == RouteType.UNSUPPORTED:
            return BrainRouteDecision(
                brain_type=BrainType.FAST,
                confidence=0.5,
                reasoning="Unsupported capability, using fast model for response",
                required_capabilities=[AgentCapability.GENERAL],
            )

        if intent_decision.route_type == RouteType.TOOL:
            return self._route_tool_request(text, intent_decision, context)

        if intent_decision.route_type == RouteType.CONVERSATIONAL:
            return self._route_conversational(text, context)

        return self._route_complex(text, context)

    def _route_tool_request(
        self,
        text: str,
        intent_decision: RouteDecision,
        context: Optional[Dict[str, Any]],
    ) -> BrainRouteDecision:
        tool_name = intent_decision.target or ""

        if any(kw in tool_name.lower() for kw in ["browser", "click", "mouse", "type", "open_app"]):
            return BrainRouteDecision(
                brain_type=BrainType.COMPUTER,
                confidence=0.9,
                reasoning=f"Computer control tool requested: {tool_name}",
                required_capabilities=[AgentCapability.GENERAL],
                metadata={"tool": tool_name},
            )

        if any(kw in tool_name.lower() for kw in ["file", "read", "write", "search"]):
            return BrainRouteDecision(
                brain_type=BrainType.CODING,
                confidence=0.8,
                reasoning=f"File operation requested: {tool_name}",
                required_capabilities=[AgentCapability.CODING],
                metadata={"tool": tool_name},
            )

        return BrainRouteDecision(
            brain_type=BrainType.FAST,
            confidence=0.7,
            reasoning=f"Tool request: {tool_name}",
            required_capabilities=[AgentCapability.GENERAL],
            metadata={"tool": tool_name},
        )

    def _route_conversational(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
    ) -> BrainRouteDecision:
        scores = self._score_brain_types(text)

        if scores["planning"] > 0.6:
            return BrainRouteDecision(
                brain_type=BrainType.PLANNING,
                confidence=scores["planning"],
                reasoning="Planning-related request detected",
                required_capabilities=[AgentCapability.TASK],
            )

        if scores["verification"] > 0.5:
            return BrainRouteDecision(
                brain_type=BrainType.VERIFICATION,
                confidence=scores["verification"],
                reasoning="Verification request detected",
                required_capabilities=[AgentCapability.GENERAL],
            )

        if scores["computer"] > 0.5:
            return BrainRouteDecision(
                brain_type=BrainType.COMPUTER,
                confidence=scores["computer"],
                reasoning="Computer control request detected",
                required_capabilities=[AgentCapability.GENERAL],
            )

        if scores["research"] > 0.5:
            return BrainRouteDecision(
                brain_type=BrainType.RESEARCH,
                confidence=scores["research"],
                reasoning="Research request detected",
                required_capabilities=[AgentCapability.RESEARCH],
            )

        if scores["coding"] > 0.5:
            return BrainRouteDecision(
                brain_type=BrainType.CODING,
                confidence=scores["coding"],
                reasoning="Coding request detected",
                required_capabilities=[AgentCapability.CODING],
            )

        return BrainRouteDecision(
            brain_type=BrainType.FAST,
            confidence=0.7,
            reasoning="General conversational request",
            required_capabilities=[AgentCapability.GENERAL],
        )

    def _route_complex(
        self,
        text: str,
        context: Optional[Dict[str, Any]],
    ) -> BrainRouteDecision:
        has_complexity_indicators = any(
            phrase in text for phrase in [
                "and then", "first", "after that", "next",
                "multiple", "several", "steps", "workflow",
            ]
        )

        if has_complexity_indicators:
            scores = self._score_brain_types(text)
            if scores["planning"] >= 0.4:
                return BrainRouteDecision(
                    brain_type=BrainType.PLANNING,
                    confidence=0.85,
                    reasoning="Complex multi-step request routed to Planning Brain",
                    required_capabilities=[AgentCapability.TASK],
                )

        scores = self._score_brain_types(text)
        max_score = max(scores.values())

        if max_score < 0.4:
            return BrainRouteDecision(
                brain_type=BrainType.PLANNING,
                confidence=0.6,
                reasoning="Complex request routed to Planning Brain for decomposition",
                required_capabilities=[AgentCapability.TASK],
            )

        return self._route_conversational(text, context)

    def _score_brain_types(self, text: str) -> Dict[str, float]:
        scores: Dict[str, float] = {
            "planning": 0.0,
            "research": 0.0,
            "coding": 0.0,
            "computer": 0.0,
            "verification": 0.0,
        }

        for kw in self.PLANNING_KEYWORDS:
            if kw in text:
                scores["planning"] += 0.15

        for kw in self.RESEARCH_KEYWORDS:
            if kw in text:
                scores["research"] += 0.15

        for kw in self.CODING_KEYWORDS:
            if kw in text:
                scores["coding"] += 0.15

        for kw in self.COMPUTER_KEYWORDS:
            if kw in text:
                scores["computer"] += 0.15

        for kw in self.VERIFICATION_KEYWORDS:
            if kw in text:
                scores["verification"] += 0.2

        for key in scores:
            scores[key] = min(scores[key], 1.0)

        return scores

    def should_use_planning(self, user_input: str) -> bool:
        """Determine if the Planning Brain should be used first.

        Complex goals should always go through Planning Brain first.
        """
        text = user_input.lower()

        complexity_indicators = [
            " and ", " then ", " after ", " multiple ",
            " steps", " workflow", " execute", " plan",
        ]

        has_complexity = any(ind in text for ind in complexity_indicators)
        has_planning_kw = any(kw in text for kw in self.PLANNING_KEYWORDS)

        return has_complexity or has_planning_kw


__all__ = ["BrainType", "BrainRouteDecision", "BrainRouter"]
