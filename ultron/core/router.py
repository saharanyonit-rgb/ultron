"""Intent Router for JARVIS / Ultron.

Determines the execution path for a user request without executing it.
Categorizes requests into:
- CONVERSATIONAL: General questions, chat, knowledge retrieval
- TOOL: Direct single-tool invocation
- AGENT: Multi-step tool dispatch loop
- UNSUPPORTED: Out-of-scope capabilities
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ultron.llm.base import LLMProvider, ProviderResult
from ultron.tools.base import Tool

logger = logging.getLogger("ultron.router")


class RouteType(str, Enum):
    CONVERSATIONAL = "conversational"
    TOOL = "tool"
    AGENT = "agent"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RouteDecision:
    """Strongly typed routing result produced by the Intent Router."""

    route_type: RouteType
    target: Optional[str] = None
    confidence: float = 1.0
    reasoning: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)


# Known out-of-scope capability patterns for V1
UNSUPPORTED_PATTERNS: List[tuple[Set[str], str]] = [
    ({"mouse", "cursor", "click", "drag"}, "Mouse and cursor automation is not supported in V1."),
    ({"speak", "voice", "audio", "microphone", "listen"}, "Voice and audio processing is not supported in V1."),
    ({"webcam", "camera", "video"}, "Camera and video processing is not supported in V1."),
    ({"shell", "terminal command", "powershell script", "bash"}, "Arbitrary shell/script execution is not supported in V1 for security."),
    ({"train", "fine-tune", "local model", "ollama"}, "Local model training and Ollama are out of scope."),
]

# Fast deterministic tool keyword mappings
TOOL_KEYWORD_MAP: Dict[str, List[str]] = {
    "get_system_info": ["system info", "sysinfo", "cpu usage", "ram info", "disk space", "memory info", "uptime"],
    "take_screenshot": ["screenshot", "take screenshot", "capture screen", "screen shot"],
    "get_clipboard": ["get clipboard", "read clipboard", "clipboard content", "paste clipboard"],
    "set_clipboard": ["set clipboard", "copy to clipboard", "write clipboard"],
    "open_url": ["open url", "open website", "browse to", "open link"],
    "open_app": ["open app", "launch app", "run app", "start notepad", "open notepad", "open calc", "open explorer",
                 "open chrome", "open google chrome", "open vscode", "open visual studio code",
                 "launch chrome", "launch vscode"],
    "close_app": ["close app", "stop app", "kill process", "close notepad", "close calc"],
    "read_file": ["read file", "cat file", "file content"],
    "create_file": ["create file", "write file", "make file", "save file"],
    "search_files": ["search files", "find files", "glob files", "list files"],
    "remember": ["remember that", "remember this", "my name is", "call me", "i prefer",
                 "note this down", "keep in mind", "don't forget that", "do not forget"],
    "recall": ["what do you know about me", "do you remember", "what did i tell you",
               "what did we discuss", "what do you remember", "recall"],
    "list_memories": ["what do you remember", "list what you know", "show your memories",
                      "what memories", "list memories"],
    "forget": ["forget that", "forget what i said", "delete that memory", "forget",
               "stop remembering"],
    "play_song": ["play the song", "play a song", "play that song", "play songs",
                  "play some music", "play music", "play a music", "i want to hear",
                  "turn on music", "start the song"],
    "github_search": ["search github", "find repos", "github repos", "search repositories",
                      "find code on github", "github repositories"],
    "github_clone": ["clone repo", "clone repository", "download repo", "clone from github",
                     "get this repo", "clone github"],
    "github_create_repo": ["create a github repo", "create github repository", "publish to github",
                          "new repository on github", "create a repository", "upload to github"],
    "github_push": ["push to github", "push to remote", "git push", "push changes",
                    "upload commits"],
    "github_pull": ["pull from github", "pull latest", "git pull", "update from remote"],
    "generate_ui": ["generate ui", "design a page", "design a website", "make a landing page",
                    "ui design", "design an interface", "make an animated page",
                    "design a dashboard", "generate html design"],
    "search_ui_design": ["ui style", "ui/ux", "design system", "color palette", "font pairing",
                         "typography pairing", "charts recommendation", "ux guideline",
                         "landing page pattern", "ui variations"],
}


class IntentRouter:
    """Classifies user intent and selects an execution path for the Brain.

    Determines WHERE a request should be executed without performing the execution.
    """

    def __init__(
        self,
        tools: Optional[List[Tool]] = None,
        provider: Optional[LLMProvider] = None,
        min_confidence: float = 0.6,
        use_llm_classification: bool = False,
    ) -> None:
        self._tools = {t.name: t for t in (tools or [])}
        self._provider = provider
        self._min_confidence = min_confidence
        self._use_llm_classification = use_llm_classification

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

        # 1. Fast deterministic check: Unsupported out-of-scope capabilities
        for keywords, reason in UNSUPPORTED_PATTERNS:
            if any(kw in text for kw in keywords):
                logger.info("Deterministic route: UNSUPPORTED ('%s')", reason)
                return RouteDecision(
                    route_type=RouteType.UNSUPPORTED,
                    confidence=1.0,
                    reasoning=reason,
                )

        # 2. Fast deterministic check: Multi-step agent route
        if any(w in text for w in ["and then", "first ", "after that", "then "]):
            logger.info("Deterministic route: AGENT (multi-step workflow)")
            return RouteDecision(
                route_type=RouteType.AGENT,
                target="agent_loop",
                confidence=0.85,
                reasoning="Complex or multi-step request routed to agent loop.",
            )

        # 3. Fast deterministic check: Known tool pattern match
        for tool_name, keywords in TOOL_KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                if tool_name in self._tools or not self._tools:
                    logger.info("Deterministic route: TOOL (%s)", tool_name)
                    return RouteDecision(
                        route_type=RouteType.TOOL,
                        target=tool_name,
                        confidence=0.95,
                        reasoning=f"Matched known tool keyword for '{tool_name}'.",
                    )
                else:
                    logger.warning("Matched tool '%s' but tool is not in registry", tool_name)
                    return RouteDecision(
                        route_type=RouteType.UNSUPPORTED,
                        confidence=0.9,
                        reasoning=f"Tool '{tool_name}' is not registered in the tool registry.",
                    )

        # 4. LLM provider classification if explicitly enabled
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
                    return llm_decision
            except Exception as exc:
                logger.error("LLM classification failed: %s", exc)
                return RouteDecision(
                    route_type=RouteType.CONVERSATIONAL,
                    confidence=0.3,
                    reasoning=f"LLM classification failure ({type(exc).__name__}); fallback to general conversation.",
                )

        # Default fallback: Conversational query
        # Guard: self-introduction patterns should ALWAYS be conversational
        conversational_patterns = [
            "my name is", "i'm ", "i am ", "call me", "you can call me",
            "name's ", "that's me", "this is ", "i'm called",
        ]
        for pattern in conversational_patterns:
            if pattern in text:
                logger.info("Deterministic route: CONVERSATIONAL (self-introduction guard)")
                return RouteDecision(
                    route_type=RouteType.CONVERSATIONAL,
                    confidence=0.95,
                    reasoning=f"Detected self-introduction pattern '{pattern}'.",
                )

        logger.info("Default route: CONVERSATIONAL")
        return RouteDecision(
            route_type=RouteType.CONVERSATIONAL,
            confidence=0.8,
            reasoning="General query routed to conversational LLM handler.",
        )

    def _classify_with_llm(self, user_input: str) -> Optional[RouteDecision]:
        """Attempt LLM-assisted classification when available."""
        prompt = (
            f"Classify the following user input into exactly one category: [CONVERSATIONAL, TOOL, AGENT, UNSUPPORTED].\n"
            f"Input: \"{user_input}\"\n"
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
]
