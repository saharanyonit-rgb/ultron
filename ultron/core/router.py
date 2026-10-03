"""Intent Router for JARVIS / Ultron.

Determines the execution path for a user request without executing it.
Categorizes requests into:
- CONVERSATIONAL: General questions, chat, knowledge retrieval
- TOOL: Direct single-tool invocation
- AGENT: Multi-step tool dispatch loop
- UNSUPPORTED: Out-of-scope capabilities

Routing is derived entirely from tool metadata (`ToolCatalog`). There is no
hand-maintained tool keyword table: adding a tool and giving it `keywords` is
what makes it routable, which is what keeps the router from claiming a
capability is unsupported while that capability sits in the registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ultron.llm.base import LLMProvider
from ultron.tools.base import Tool
from ultron.tools.catalog import ToolCatalog, build_catalog

logger = logging.getLogger("ultron.router")


class RouteType(StrEnum):
    CONVERSATIONAL = "conversational"
    TOOL = "tool"
    AGENT = "agent"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RouteDecision:
    """Strongly typed routing result produced by the Intent Router."""

    route_type: RouteType
    target: str | None = None
    confidence: float = 1.0
    reasoning: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


# Capabilities the project genuinely does not implement. These are checked
# against the catalog at import time by `validate_out_of_scope`: if a tool ever
# starts covering one of these, the entry is a bug and raises instead of
# silently refusing a request the assistant can actually fulfill.
OUT_OF_SCOPE: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset({"train a model", "fine-tune", "fine tune", "ollama"}),
        "Training or running a local model server is not implemented.",
    ),
)


def validate_out_of_scope(catalog: ToolCatalog) -> None:
    """Fail loudly if a declared-unsupported capability has a tool for it."""
    for keywords, reason in OUT_OF_SCOPE:
        for keyword in sorted(keywords):
            match = catalog.best_phrase_match(keyword)
            if match is not None:
                tool_name, phrase = match
                raise AssertionError(
                    f"Contradiction: {keyword!r} is declared out of scope "
                    f"({reason!r}) but registered tool {tool_name!r} matches it "
                    f"via phrase {phrase!r}. Remove the entry or the tool."
                )


_MULTI_STEP_MARKERS = ("and then", "after that", "then ", "first ", "finally ")

# Self-introduction is chat, even though it can contain a keyword ("call me").
_CONVERSATIONAL_PATTERNS = (
    "my name is",
    "i'm ",
    "i am ",
    "call me",
    "you can call me",
    "name's ",
    "that's me",
    "this is ",
    "i'm called",
)


class IntentRouter:
    """Classifies user intent and selects an execution path for the Brain.

    Determines WHERE a request should be executed without performing the
    execution. Capability knowledge comes from `ToolCatalog`; this class holds
    no list of tool names.
    """

    def __init__(
        self,
        tools: list[Tool] | None = None,
        provider: LLMProvider | None = None,
        min_confidence: float = 0.6,
        use_llm_classification: bool = False,
        catalog: ToolCatalog | None = None,
    ) -> None:
        if catalog is not None:
            self._catalog = catalog
        elif tools:
            self._catalog = build_catalog(list(tools))
        else:
            self._catalog = build_catalog()
            validate_out_of_scope(self._catalog)
        self._provider = provider
        self._min_confidence = min_confidence
        self._use_llm_classification = use_llm_classification

    @property
    def catalog(self) -> ToolCatalog:
        return self._catalog

    def route(self, user_input: str) -> RouteDecision:
        """Analyze user input and determine the execution route.

        Does NOT execute tools or run side-effects.
        """
        if not isinstance(user_input, str) or not user_input.strip():
            logger.warning("Router received empty or invalid input")
            return RouteDecision(
                route_type=RouteType.CONVERSATIONAL,
                confidence=0.0,
                reasoning="Empty or non-string input provided.",
            )

        text = user_input.strip().lower()

        # 1. Self-introduction is conversation, checked first so that a keyword
        #    such as "call me" cannot drag it into the tool path.
        for pattern in _CONVERSATIONAL_PATTERNS:
            if pattern in text:
                logger.info("Deterministic route: CONVERSATIONAL (self-introduction guard)")
                return RouteDecision(
                    route_type=RouteType.CONVERSATIONAL,
                    confidence=0.95,
                    reasoning=f"Detected self-introduction pattern '{pattern}'.",
                )

        # 2. Capabilities that are genuinely not implemented.
        for keywords, reason in OUT_OF_SCOPE:
            if any(kw in text for kw in keywords):
                logger.info("Deterministic route: UNSUPPORTED ('%s')", reason)
                return RouteDecision(
                    route_type=RouteType.UNSUPPORTED,
                    confidence=1.0,
                    reasoning=reason,
                )

        # 3. Multi-step agent route.
        if any(marker in text for marker in _MULTI_STEP_MARKERS):
            logger.info("Deterministic route: AGENT (multi-step workflow)")
            return RouteDecision(
                route_type=RouteType.AGENT,
                target="agent_loop",
                confidence=0.85,
                reasoning="Complex or multi-step request routed to agent loop.",
            )

        # 4. Exact phrase match against tool metadata, most specific phrase first.
        match = self._catalog.best_phrase_match(text)
        if match is not None:
            tool_name, phrase = match
            logger.info("Deterministic route: TOOL (%s via %r)", tool_name, phrase)
            return RouteDecision(
                route_type=RouteType.TOOL,
                target=tool_name,
                confidence=0.95,
                reasoning=f"Matched tool metadata phrase '{phrase}' for '{tool_name}'.",
            )

        # 5. Weaker token-overlap match: enough signal to need tools, not enough
        #    for a confident single-tool call.
        #
        #    This bar is deliberately high. Coverage alone is useless in a short
        #    sentence — one incidental word reaches 50% — and description tokens
        #    carry common nouns ("story", "workspace"), so "tell me a story
        #    about space" overlaps `recall` twice. Diverting ordinary chat into
        #    a tool-oriented agent loop is a worse failure than deferring to the
        #    LLM, which can still call any tool it likes. Three distinct tokens
        #    is the point where the overlap is real signal.
        for tool_name, score, overlap in self._catalog.score_tokens(text):
            if overlap >= 3 and score >= 0.5:
                logger.info(
                    "Deterministic route: AGENT (token match %s=%.2f, overlap=%d)",
                    tool_name,
                    score,
                    overlap,
                )
                return RouteDecision(
                    route_type=RouteType.AGENT,
                    target=tool_name,
                    confidence=min(0.8, score),
                    reasoning=(
                        f"Partial metadata overlap with '{tool_name}'; "
                        "routed to agent loop to let the model compose arguments."
                    ),
                )
            break

        # 6. LLM provider classification if explicitly enabled.
        if self._use_llm_classification and self._provider is not None:
            try:
                llm_decision = self._classify_with_llm(user_input)
                if llm_decision is not None:
                    if llm_decision.confidence < self._min_confidence:
                        logger.info(
                            "LLM confidence (%.2f) below threshold (%.2f), falling back to CONVERSATIONAL",
                            llm_decision.confidence,
                            self._min_confidence,
                        )
                        return RouteDecision(
                            route_type=RouteType.CONVERSATIONAL,
                            confidence=llm_decision.confidence,
                            reasoning=f"Low confidence LLM classification ({llm_decision.confidence:.2f}); fallback to general conversation.",
                        )
                    if (
                        llm_decision.route_type is RouteType.TOOL
                        and llm_decision.target
                        and not self._catalog.get(llm_decision.target)
                    ):
                        # Never let the model name a tool that is not registered.
                        return RouteDecision(
                            route_type=RouteType.UNSUPPORTED,
                            confidence=llm_decision.confidence,
                            reasoning=(
                                f"Tool '{llm_decision.target}' is not registered; "
                                "refusing the call."
                            ),
                        )
                    return llm_decision
            except Exception as exc:
                logger.error("LLM classification failed: %s", exc)
                return RouteDecision(
                    route_type=RouteType.CONVERSATIONAL,
                    confidence=0.3,
                    reasoning=f"LLM classification failure ({type(exc).__name__}); fallback to general conversation.",
                )

        # Default fallback: conversational query.
        logger.info("Default route: CONVERSATIONAL")
        return RouteDecision(
            route_type=RouteType.CONVERSATIONAL,
            confidence=0.8,
            reasoning="General query routed to conversational LLM handler.",
        )

    def _classify_with_llm(self, user_input: str) -> RouteDecision | None:
        """Attempt LLM-assisted classification when available."""
        if self._provider is None:
            # No provider wired: report "no decision" so the caller keeps its
            # deterministic fallbacks, matching the other failure paths here.
            return None

        prompt = (
            f"Classify the following user input into exactly one category: [CONVERSATIONAL, TOOL, AGENT, UNSUPPORTED].\n"
            f'Input: "{user_input}"\n'
            f"Format response as: CATEGORY|TARGET|CONFIDENCE|REASON"
        )
        res = self._provider.complete(prompt, tools=[])
        if not res or not res.text:
            return None

        parts = [p.strip() for p in res.text.strip().split("|")]
        if len(parts) >= 1:
            cat_str = parts[0].upper()
            try:
                route_type = RouteType[cat_str]
            except KeyError:
                return None
            target = parts[1] if len(parts) > 1 and parts[1] else None
            try:
                conf = float(parts[2]) if len(parts) > 2 else 0.8
            except ValueError:
                conf = 0.8
            reasoning = parts[3] if len(parts) > 3 else "LLM classified"
            return RouteDecision(
                route_type=route_type,
                target=target,
                confidence=conf,
                reasoning=reasoning,
            )
        return None


__all__ = [
    "IntentRouter",
    "RouteDecision",
    "RouteType",
    "OUT_OF_SCOPE",
    "validate_out_of_scope",
]
