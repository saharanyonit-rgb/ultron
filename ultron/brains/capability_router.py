"""Capability-Based Brain Router for JARVIS Phase 7.7.1.

Intelligent routing system with calibrated confidence, context-awareness,
and ambiguity detection. Prefers DETERMINISTIC matching over LLM classification.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ultron.brains.capability_router")


class Intent(str, Enum):
    """High-level user intent categories."""
    GREETING = "greeting"
    CONVERSATION = "conversation"
    COMPUTER_CONTROL = "computer_control"
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    VERIFICATION = "verification"
    MULTI_AGENT = "multi_agent"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class Complexity(str, Enum):
    """Task complexity levels."""
    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class RiskLevel(str, Enum):
    """Risk levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class BrainCapability:
    """A single capability that a brain provides."""
    name: str
    description: str
    keywords: Set[str] = field(default_factory=set)
    required_tools: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class BrainCapabilities:
    """Structured capabilities for a brain type."""
    brain_type: str
    primary_intents: Set[Intent]
    capabilities: Tuple[BrainCapability, ...]
    compatible_risk_levels: Set[RiskLevel]
    max_agent_transitions: int = 3
    preferred_complexity: Set[Complexity] = field(default_factory=frozenset)


class BrainCapabilityRegistry:
    """Registry of capabilities for all brain types."""

    PLANNING = BrainCapabilities(
        brain_type="planning",
        primary_intents={Intent.PLANNING, Intent.MULTI_AGENT},
        capabilities=(
            BrainCapability(
                name="planning",
                description="Goal decomposition and task planning",
                keywords={"plan", "strategy", "workflow", "steps", "execute", "coordinate",
                         "decompose", "break down", "roadmap", "milestone", "sequence",
                         "multiple steps", "parallel", "dependencies", "subtask"},
                required_tools=set(),
            ),
            BrainCapability(
                name="task_decomposition",
                description="Breaking complex goals into actionable tasks",
                keywords={"decompose", "break down", "split", "divide", "organize"},
                required_tools=set(),
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH},
        max_agent_transitions=5,
        preferred_complexity={Complexity.MODERATE, Complexity.COMPLEX, Complexity.VERY_COMPLEX},
    )

    RESEARCH = BrainCapabilities(
        brain_type="research",
        primary_intents={Intent.RESEARCH},
        capabilities=(
            BrainCapability(
                name="research",
                description="Information gathering and analysis",
                keywords={"research", "investigate", "explore", "survey", "study",
                         "find information", "look up", "analyze", "compare",
                         "evaluate", "facts", "sources", "information"},
                required_tools={"read_file", "search_files", "open_url"},
            ),
            BrainCapability(
                name="web_search",
                description="Web-based information retrieval",
                keywords={"search the web", "find online", "google", "web search",
                         "browse", "internet"},
                required_tools={"open_url"},
            ),
            BrainCapability(
                name="source_analysis",
                description="Analyzing and citing sources",
                keywords={"cite", "source", "reference", "evidence", "according to"},
                required_tools=set(),
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW, RiskLevel.MEDIUM},
        max_agent_transitions=3,
        preferred_complexity={Complexity.SIMPLE, Complexity.MODERATE},
    )

    CODING = BrainCapabilities(
        brain_type="coding",
        primary_intents={Intent.CODING},
        capabilities=(
            BrainCapability(
                name="code_analysis",
                description="Analyzing existing code",
                keywords={"code", "function", "class", "module", "repository", "file",
                         "inspect", "analyze code", "understand code", "review code"},
                required_tools={"read_file", "search_files"},
            ),
            BrainCapability(
                name="debugging",
                description="Finding and fixing bugs",
                keywords={"bug", "fix", "debug", "error", "issue", "problem", "crash",
                         "failing", "broken", "incorrect"},
                required_tools={"read_file", "search_files"},
            ),
            BrainCapability(
                name="code_generation",
                description="Creating new code",
                keywords={"implement", "create", "write code", "add feature", "develop",
                         "generate code", "programming"},
                required_tools={"create_file", "read_file"},
            ),
            BrainCapability(
                name="refactoring",
                description="Restructuring existing code",
                keywords={"refactor", "restructure", "improve code", "optimize"},
                required_tools={"read_file", "create_file"},
            ),
            BrainCapability(
                name="testing",
                description="Testing and validation",
                keywords={"test", "run tests", "testing", "validate", "verify"},
                required_tools=set(),
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH},
        max_agent_transitions=4,
        preferred_complexity={Complexity.SIMPLE, Complexity.MODERATE, Complexity.COMPLEX},
    )

    COMPUTER = BrainCapabilities(
        brain_type="computer",
        primary_intents={Intent.COMPUTER_CONTROL},
        capabilities=(
            BrainCapability(
                name="desktop_control",
                description="Desktop application control",
                keywords={"open", "close", "launch", "start", "stop", "application",
                         "desktop"},
                required_tools={"open_app", "close_app"},
            ),
            BrainCapability(
                name="browser_control",
                description="Web browser control",
                keywords={"chrome", "browser", "navigate", "browse", "click", "type",
                         "open website", "go to"},
                required_tools={"navigate_url", "open_url", "click_element"},
            ),
            BrainCapability(
                name="screenshot_analysis",
                description="Taking and analyzing screenshots",
                keywords={"screenshot", "capture screen", "screen shot", "visual"},
                required_tools={"take_screenshot"},
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH},
        max_agent_transitions=3,
        preferred_complexity={Complexity.TRIVIAL, Complexity.SIMPLE, Complexity.MODERATE},
    )

    VERIFICATION = BrainCapabilities(
        brain_type="verification",
        primary_intents={Intent.VERIFICATION},
        capabilities=(
            BrainCapability(
                name="verification",
                description="Verifying task results",
                keywords={"verify", "check", "confirm", "validate", "test", "ensure",
                         "did it work", "was it successful", "confirm that", "inspect",
                         "success", "failed", "result", "output"},
                required_tools=set(),
            ),
            BrainCapability(
                name="evidence_analysis",
                description="Analyzing evidence and output",
                keywords={"evidence", "proof", "output", "result", "status"},
                required_tools=set(),
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL},
        max_agent_transitions=2,
        preferred_complexity={Complexity.TRIVIAL, Complexity.SIMPLE, Complexity.MODERATE},
    )

    FAST = BrainCapabilities(
        brain_type="fast",
        primary_intents={Intent.GREETING, Intent.CONVERSATION},
        capabilities=(
            BrainCapability(
                name="conversation",
                description="General conversation and greetings",
                keywords={"hello", "hi", "hey", "thanks", "thank you", "bye", "goodbye",
                         "how are you", "what's up", "greetings", "nice to meet"},
                required_tools=set(),
            ),
        ),
        compatible_risk_levels={RiskLevel.LOW},
        max_agent_transitions=0,
        preferred_complexity={Complexity.TRIVIAL},
    )

    @classmethod
    def get_all_capabilities(cls) -> Dict[str, BrainCapabilities]:
        return {
            "planning": cls.PLANNING,
            "research": cls.RESEARCH,
            "coding": cls.CODING,
            "computer": cls.COMPUTER,
            "verification": cls.VERIFICATION,
            "fast": cls.FAST,
        }


@dataclass
class TaskRequirements:
    """Structured representation of what a task requires."""
    intent: Intent
    complexity: Complexity
    required_capabilities: Set[str]
    required_tools: Set[str]
    risk_level: RiskLevel
    verification_required: bool = False
    multi_agent_required: bool = False
    workflow_steps: List[str] = field(default_factory=list)
    context_preserved: bool = False
    is_follow_up: bool = False
    previous_brain: Optional[str] = None
    ambiguous: bool = False
    ambiguity_reason: str = ""


@dataclass
class RoutingDecision:
    """Structured routing decision with full metadata."""
    selected_brain: str
    confidence: float
    best_score: float = 0.0
    second_best_score: float = 0.0
    score_margin: float = 0.0
    matched_capabilities: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    intent: Intent = Intent.UNKNOWN
    complexity: Complexity = Complexity.MODERATE
    workflow_required: bool = False
    workflow_steps: List[str] = field(default_factory=list)
    alternatives: List[Tuple[str, float]] = field(default_factory=list)
    reason: str = ""
    ambiguity: bool = False
    ambiguity_reason: str = ""
    missing_information: List[str] = field(default_factory=list)
    candidate_agents: List[str] = field(default_factory=list)
    needs_llm_classification: bool = False
    classifier_source: str = "deterministic"
    routing_latency_ms: float = 0.0
    routing_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingScore:
    """Score breakdown for a single brain."""
    brain_type: str
    total_score: float
    capability_match: float = 0.0
    intent_match: float = 0.0
    tool_match: float = 0.0
    complexity_match: float = 0.0
    risk_match: float = 0.0
    context_match: float = 0.0


def _word_boundary_match(text: str, keyword: str) -> bool:
    """Check if keyword matches with proper word boundaries."""
    pattern = r'\b' + re.escape(keyword) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def _tokenize_words(text: str) -> Set[str]:
    """Extract words from text."""
    words = re.findall(r'\b\w+\b', text.lower())
    return set(words)


class AmbiguousTaskError(Exception):
    """Raised when task is too ambiguous to route deterministically."""
    def __init__(self, reason: str, candidates: List[str]):
        self.reason = reason
        self.candidates = candidates
        super().__init__(f"Ambiguous task: {reason}")


class CapabilityBasedRouter:
    """Intelligent router using capability-based matching.

    Prefers deterministic matching over LLM classification.
    Uses structured capability models for routing decisions.
    """

    TRIVIAL_PATTERNS = [
        r"^\s*hi\s*$",
        r"^\s*hello\s*$",
        r"^\s*hey\s*$",
        r"^\s*thanks?\s*$",
        r"^\s*thank you\s*$",
        r"^\s*bye\s*$",
        r"^\s*goodbye\s*$",
        r"^\s*how are you\s*\??$",
        r"^\s*what'?s up\s*\??$",
        r"^\s*nice to meet you\s*$",
        r"^\s*greetings?\s*$",
        r"^\s*hi there\s*$",
        r"^\s*hello there\s*$",
    ]

    AMBIGUOUS_PATTERNS = [
        r"^\s*(check|fix|handle|look into|do|process)\s+(this|that|it|them)\s*$",
        r"^\s*(find|search|get)\s+(it|that|this|them)\s*$",
        r"^\s*(tell me|talk about)\s*$",
    ]

    FOLLOW_UP_PATTERNS = [
        r"^\s*(fix|repair|address)\s+(it|them|that|the issue)\s*$",
        r"^\s*(fix|repair|address)\s+(this|them)\s*$",
        r"^\s*(summarize|summary)\s+(it|that|this)\s*$",
        r"^\s*(which|what)\s+(is|was|should)\s+",
        r"^\s*(explain|tell me more about)\s+",
        r"^\s*(continue|keep going|proceed)\s*$",
    ]

    REFERRING_EXPRESSIONS = {"it", "this", "that", "them", "the issue", "the bug",
                            "the result", "the comparison", "the analysis"}

    def __init__(
        self,
        available_tools: Optional[Set[str]] = None,
        use_llm_fallback: bool = False,
        confidence_threshold: float = 0.35,
        llm_classifier: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        self._available_tools = available_tools or set()
        self._use_llm_fallback = use_llm_fallback
        self._confidence_threshold = confidence_threshold
        self._llm_classifier = llm_classifier
        self._previous_context: Optional[Dict[str, Any]] = None
        self._transition_history: List[str] = []
        self._capability_registry = BrainCapabilityRegistry.get_all_capabilities()
        self._llm_calls = 0

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

    def reset_llm_calls(self) -> None:
        self._llm_calls = 0

    def route(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> RoutingDecision:
        """Route a user request to the appropriate brain.

        Args:
            user_input: The user's request
            context: Optional execution context

        Returns:
            RoutingDecision with full routing metadata
        """
        start_time = time.time()

        if context:
            self._previous_context = context

        text = user_input.lower().strip()

        if self._is_trivial(text):
            return self._route_trivial(text, start_time)

        task_req = self._analyze_task(text, context)

        if task_req.is_follow_up and task_req.previous_brain:
            routing_decision = self._route_with_context(task_req, start_time)
            if routing_decision:
                return routing_decision

        if self._is_ambiguous(text) and not self._previous_context:
            ambiguous_decision = self._handle_ambiguous(text, start_time)
            if self._use_llm_fallback and self._llm_classifier:
                return self._route_with_llm_fallback(user_input, ambiguous_decision, start_time)
            return ambiguous_decision

        if task_req.multi_agent_required:
            return self._route_multi_agent(task_req, start_time)

        if task_req.ambiguous:
            return self._handle_ambiguous(text, start_time, task_req.ambiguity_reason)

        routing_decision = self._find_best_brain(task_req, start_time)

        if routing_decision.confidence < self._confidence_threshold and self._use_llm_fallback:
            return self._route_with_llm_fallback(user_input, routing_decision, start_time)

        return routing_decision

    def _is_trivial(self, text: str) -> bool:
        """Check if request is trivial (fast path)."""
        for pattern in self.TRIVIAL_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    def _is_ambiguous(self, text: str) -> bool:
        """Check if request is too ambiguous without context."""
        for pattern in self.AMBIGUOUS_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        return False

    def _route_trivial(self, text: str, start_time: float) -> RoutingDecision:
        """Route trivial requests to fast path."""
        latency = (time.time() - start_time) * 1000
        return RoutingDecision(
            selected_brain="fast",
            confidence=0.95,
            best_score=0.95,
            second_best_score=0.0,
            score_margin=0.95,
            matched_capabilities=["conversation"],
            required_tools=[],
            intent=Intent.GREETING,
            complexity=Complexity.TRIVIAL,
            workflow_required=False,
            reason="Trivial request - fast path",
            classifier_source="deterministic",
            routing_latency_ms=latency,
        )

    def _handle_ambiguous(
        self,
        text: str,
        start_time: float,
        reason: str = "Insufficient information to determine intent",
    ) -> RoutingDecision:
        """Handle ambiguous tasks."""
        latency = (time.time() - start_time) * 1000

        candidates = []
        if self._previous_context and "previous_brain" in self._previous_context:
            candidates = [self._previous_context.get("previous_brain", "fast")]
        else:
            candidates = ["fast", "planning"]

        return RoutingDecision(
            selected_brain="fast",
            confidence=0.1,
            best_score=0.1,
            second_best_score=0.05,
            score_margin=0.05,
            matched_capabilities=[],
            required_tools=[],
            intent=Intent.AMBIGUOUS,
            complexity=Complexity.MODERATE,
            workflow_required=False,
            reason=reason,
            ambiguity=True,
            ambiguity_reason=reason,
            missing_information=["specific subject or context"],
            candidate_agents=candidates,
            classifier_source="deterministic",
            routing_latency_ms=latency,
        )

    def _analyze_task(self, text: str, context: Optional[Dict[str, Any]]) -> TaskRequirements:
        """Analyze task and determine requirements."""
        is_follow_up = bool(re.match(r'^\s*(fix|repair|summarize|explain|tell|which|what|continue)', text))

        previous_brain = None
        if context and "previous_brain" in context:
            previous_brain = context.get("previous_brain")

        if is_follow_up and previous_brain:
            return TaskRequirements(
                intent=self._infer_intent_from_context(text, previous_brain),
                complexity=Complexity.SIMPLE,
                required_capabilities=set(),
                required_tools=set(),
                risk_level=RiskLevel.LOW,
                verification_required=False,
                multi_agent_required=False,
                context_preserved=True,
                is_follow_up=True,
                previous_brain=previous_brain,
            )

        intent = self._detect_intent(text)
        complexity = self._detect_complexity(text)
        risk_level = self._detect_risk_level(text)
        required_capabilities = self._detect_required_capabilities(text, intent)
        required_tools = self._detect_required_tools(text)
        verification_required = self._detect_verification_requirement(text)
        multi_agent = self._detect_multi_agent_pattern(text)

        return TaskRequirements(
            intent=intent,
            complexity=complexity,
            required_capabilities=required_capabilities,
            required_tools=required_tools,
            risk_level=risk_level,
            verification_required=verification_required,
            multi_agent_required=multi_agent,
        )

    def _infer_intent_from_context(self, text: str, previous_brain: str) -> Intent:
        """Infer intent from context and follow-up text."""
        text_lower = text.lower()

        if previous_brain == "coding":
            if any(kw in text_lower for kw in ["fix", "repair", "address"]):
                return Intent.CODING
            if any(kw in text_lower for kw in ["summarize", "what"]):
                return Intent.VERIFICATION

        if previous_brain == "research":
            if any(kw in text_lower for kw in ["summarize", "compare"]):
                return Intent.RESEARCH

        if previous_brain == "computer":
            if any(kw in text_lower for kw in ["navigate", "open", "go to"]):
                return Intent.COMPUTER_CONTROL

        return Intent.VERIFICATION

    def _detect_intent(self, text: str) -> Intent:
        """Detect primary user intent using deterministic matching with word boundaries."""
        if _word_boundary_match(text, "hello") or _word_boundary_match(text, "hi") or \
           _word_boundary_match(text, "hey") or _word_boundary_match(text, "thanks"):
            return Intent.GREETING

        if any(_word_boundary_match(text, kw) for kw in ["open", "close", "launch", "chrome", "browser"]):
            return Intent.COMPUTER_CONTROL

        if any(_word_boundary_match(text, kw) for kw in ["navigate", "browse", "click", "type"]):
            return Intent.COMPUTER_CONTROL

        if any(_word_boundary_match(text, kw) for kw in ["bug", "fix", "debug", "refactor", "implement"]):
            return Intent.CODING

        if any(_word_boundary_match(text, kw) for kw in ["code", "programming", "repository", "git", "class", "function"]):
            return Intent.CODING

        if any(_word_boundary_match(text, kw) for kw in ["research", "investigate", "analyze", "compare"]):
            return Intent.RESEARCH

        if any(_word_boundary_match(text, kw) for kw in ["search", "find information", "look up"]):
            return Intent.RESEARCH

        if any(_word_boundary_match(text, kw) for kw in ["plan", "strategy", "workflow", "coordinate", "decompose", "break down", "subtask", "milestone"]):
            return Intent.PLANNING

        if any(_word_boundary_match(text, kw) for kw in ["verify", "check", "confirm", "validate"]):
            return Intent.VERIFICATION

        if any(_word_boundary_match(text, kw) for kw in ["test", "ensure", "did it work"]):
            return Intent.VERIFICATION

        if self._detect_multi_agent_pattern(text):
            return Intent.MULTI_AGENT

        return Intent.CONVERSATION

    def _detect_complexity(self, text: str) -> Complexity:
        """Detect task complexity."""
        if self._is_trivial(text):
            return Complexity.TRIVIAL

        complexity_indicators = sum(
            1 for ind in [" and ", " then ", " after that ", " next ", " multiple ", " steps", " workflow"]
            if ind in text
        )

        if complexity_indicators >= 3:
            return Complexity.VERY_COMPLEX
        elif complexity_indicators >= 2:
            return Complexity.COMPLEX
        elif complexity_indicators >= 1:
            return Complexity.MODERATE

        if any(_word_boundary_match(text, kw) for kw in ["open", "close", "launch"]):
            return Complexity.SIMPLE

        if _word_boundary_match(text, "get") and any(kw in text for kw in ["system info", "sysinfo"]):
            return Complexity.SIMPLE

        return Complexity.MODERATE

    def _detect_risk_level(self, text: str) -> RiskLevel:
        """Detect required risk level."""
        if any(_word_boundary_match(text, kw) for kw in ["delete", "remove", "drop", "destroy"]):
            return RiskLevel.CRITICAL

        if any(_word_boundary_match(text, kw) for kw in ["create", "write", "modify", "change", "update"]):
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def _detect_required_capabilities(self, text: str, intent: Intent) -> Set[str]:
        """Detect required capabilities based on intent."""
        capability_map = {
            Intent.PLANNING: {"planning", "task_decomposition"},
            Intent.RESEARCH: {"research", "web_search", "source_analysis"},
            Intent.CODING: {"code_analysis", "debugging", "code_generation", "refactoring"},
            Intent.COMPUTER_CONTROL: {"desktop_control", "browser_control", "screenshot_analysis"},
            Intent.VERIFICATION: {"verification", "evidence_analysis"},
        }
        return capability_map.get(intent, set())

    def _detect_required_tools(self, text: str) -> Set[str]:
        """Detect required tools based on text analysis with word boundaries."""
        tools = set()

        tool_patterns = {
            "read_file": ["read file", "cat file", "file content", "inspect file"],
            "create_file": ["create file", "write file", "make file", "save file"],
            "search_files": ["search files", "find files", "grep"],
            "open_app": ["open app", "launch app"],
            "close_app": ["close app", "close window"],
            "open_url": ["open url", "open website", "browse to", "go to website"],
            "navigate_url": ["navigate to", "navigate browser"],
            "take_screenshot": ["screenshot", "capture screen"],
            "get_system_info": ["system info", "sysinfo", "cpu", "memory", "disk"],
        }

        for tool_name, patterns in tool_patterns.items():
            if any(_word_boundary_match(text, p) for p in patterns):
                tools.add(tool_name)

        return tools

    def _detect_verification_requirement(self, text: str) -> bool:
        """Detect if verification is required."""
        verification_keywords = ["verify", "check if", "confirm", "make sure", "ensure",
                               "did it work", "was it successful", "validate"]
        return any(_word_boundary_match(text, kw) for kw in verification_keywords)

    def _detect_multi_agent_pattern(self, text: str) -> bool:
        """Detect if task requires multiple agents."""
        text_clean = text.replace(",", " ")

        multi_step_indicators = [" and ", " then ", " after that ", " next "]
        if sum(1 for ind in multi_step_indicators if ind in text_clean) >= 1:
            verb_count = 0
            for verb in ["research", "analyze", "compare", "evaluate", "implement", "fix", "verify", "recommend", "create", "build"]:
                if verb in text_clean:
                    verb_count += 1
            if verb_count >= 2:
                return True

        multi_agent_verbs = ["research", "analyze", "compare", "evaluate", "implement", "fix", "verify", "recommend", "create", "build"]
        verb_count = sum(1 for verb in multi_agent_verbs if _word_boundary_match(text, verb))
        if verb_count >= 2:
            return True

        return False

    def _route_with_context(self, task_req: TaskRequirements, start_time: float) -> Optional[RoutingDecision]:
        """Route using previous context for follow-up requests."""
        if task_req.previous_brain and task_req.previous_brain in self._capability_registry:
            latency = (time.time() - start_time) * 1000
            intent_name = task_req.intent.value

            return RoutingDecision(
                selected_brain=task_req.previous_brain,
                confidence=0.85,
                best_score=0.85,
                second_best_score=0.3,
                score_margin=0.55,
                matched_capabilities=[f"context:{task_req.previous_brain}", f"intent:{intent_name}"],
                required_tools=list(task_req.required_tools),
                intent=task_req.intent,
                complexity=task_req.complexity,
                workflow_required=False,
                reason=f"Follow-up request using previous {task_req.previous_brain} context",
                classifier_source="deterministic",
                routing_latency_ms=latency,
                routing_metadata={"context_used": True, "previous_brain": task_req.previous_brain},
            )
        return None

    def _route_multi_agent(self, task_req: TaskRequirements, start_time: float) -> RoutingDecision:
        """Route to Planning brain for workflow generation."""
        latency = (time.time() - start_time) * 1000

        return RoutingDecision(
            selected_brain="planning",
            confidence=0.85,
            best_score=0.85,
            second_best_score=0.4,
            score_margin=0.45,
            matched_capabilities=["planning", "task_decomposition"],
            required_tools=[],
            intent=Intent.MULTI_AGENT,
            complexity=task_req.complexity,
            workflow_required=True,
            workflow_steps=["planning", "execution", "verification"],
            reason="Multi-agent workflow detected - routing to Planning Brain",
            classifier_source="deterministic",
            routing_latency_ms=latency,
        )

    def _find_best_brain(self, task_req: TaskRequirements, start_time: float) -> RoutingDecision:
        """Find the best matching brain using capability scoring."""
        scores: List[RoutingScore] = []

        for brain_type, capabilities in self._capability_registry.items():
            score = self._score_brain(brain_type, capabilities, task_req)
            scores.append(score)

        scores.sort(key=lambda s: s.total_score, reverse=True)

        best = scores[0]
        second_best = scores[1] if len(scores) > 1 else scores[0]
        margin = best.total_score - second_best.total_score

        alternatives = [(s.brain_type, s.total_score) for s in scores[1:4]]

        self._transition_history.append(best.brain_type)

        latency = (time.time() - start_time) * 1000

        confidence = self._calculate_confidence(best, second_best, margin, task_req)

        return RoutingDecision(
            selected_brain=best.brain_type,
            confidence=confidence,
            best_score=best.total_score,
            second_best_score=second_best.total_score,
            score_margin=margin,
            matched_capabilities=self._get_matched_capabilities(best, task_req),
            required_tools=list(task_req.required_tools),
            intent=task_req.intent,
            complexity=task_req.complexity,
            workflow_required=False,
            alternatives=alternatives,
            reason=self._build_reason(best, second_best, margin, task_req),
            candidate_agents=[s.brain_type for s in scores[:3]],
            classifier_source="deterministic",
            routing_latency_ms=latency,
            routing_metadata={
                "intent_match": best.intent_match,
                "capability_match": best.capability_match,
                "tool_match": best.tool_match,
                "complexity_match": best.complexity_match,
            },
        )

    def _calculate_confidence(
        self,
        best: RoutingScore,
        second_best: RoutingScore,
        margin: float,
        task_req: TaskRequirements,
    ) -> float:
        """Calculate calibrated confidence based on multiple factors."""
        base_confidence = best.total_score

        high_confidence_boost = 0.0
        if best.intent_match > 0.9:
            high_confidence_boost = 0.15

        if task_req.intent == Intent.GREETING:
            return min(0.95, base_confidence + 0.2)

        if margin > 0.3:
            high_confidence_boost += 0.1

        if margin < 0.1:
            base_confidence = base_confidence * 0.7

        return min(0.95, max(0.1, base_confidence + high_confidence_boost))

    def _score_brain(
        self,
        brain_type: str,
        capabilities: BrainCapabilities,
        task_req: TaskRequirements,
    ) -> RoutingScore:
        """Score how well a brain matches the task requirements."""
        intent_match = 1.0 if task_req.intent in capabilities.primary_intents else 0.0

        capability_match = 0.0
        for cap in capabilities.capabilities:
            for req_cap in task_req.required_capabilities:
                if req_cap == cap.name or req_cap in {c.name for c in capabilities.capabilities}:
                    capability_match += 0.25
                    break

        tool_match = 0.0
        if task_req.required_tools:
            for req_tool in task_req.required_tools:
                if req_tool in self._available_tools:
                    for cap in capabilities.capabilities:
                        if req_tool in cap.required_tools:
                            tool_match += 0.3
                            break

        complexity_match = 0.8 if task_req.complexity in capabilities.preferred_complexity else 0.2

        risk_match = 0.6 if task_req.risk_level in capabilities.compatible_risk_levels else 0.0

        context_match = 0.0
        if task_req.is_follow_up and task_req.previous_brain == brain_type:
            context_match = 0.4

        total = (
            intent_match * 0.40 +
            capability_match * 0.20 +
            tool_match * 0.20 +
            complexity_match * 0.10 +
            risk_match * 0.05 +
            context_match * 0.05
        )

        return RoutingScore(
            brain_type=brain_type,
            total_score=min(total, 1.0),
            capability_match=capability_match,
            intent_match=intent_match,
            tool_match=tool_match,
            complexity_match=complexity_match,
            risk_match=risk_match,
            context_match=context_match,
        )

    def _get_matched_capabilities(self, score: RoutingScore, task_req: TaskRequirements) -> List[str]:
        """Get list of capabilities that matched."""
        matched = []
        if score.intent_match > 0:
            matched.append(f"intent:{task_req.intent.value}")
        if score.capability_match > 0:
            matched.append(f"capability_match:{score.capability_match:.2f}")
        if score.tool_match > 0:
            matched.append(f"tool_match:{score.tool_match:.2f}")
        return matched

    def _build_reason(
        self,
        best: RoutingScore,
        second_best: RoutingScore,
        margin: float,
        task_req: TaskRequirements,
    ) -> str:
        """Build human-readable reason for routing decision."""
        parts = [f"Intent '{task_req.intent.value}' strongly matches {best.brain_type}"]

        if margin > 0.3:
            parts.append(f"Clear winner (margin: {margin:.2f})")
        elif margin < 0.1:
            parts.append(f"Ambiguous (margin: {margin:.2f})")

        if best.intent_match > 0.9:
            parts.append("Strong intent match")
        elif best.intent_match < 0.5:
            parts.append("Weak intent match")

        return "; ".join(parts)

    def _route_with_llm_fallback(
        self,
        user_input: str,
        previous_decision: RoutingDecision,
        start_time: float,
    ) -> RoutingDecision:
        """Use LLM to assist with ambiguous routing."""
        if not self._llm_classifier:
            return previous_decision

        self._llm_calls += 1
        latency = (time.time() - start_time) * 1000

        try:
            llm_result = self._llm_classifier(user_input)

            if llm_result and "intent" in llm_result:
                intent_str = llm_result.get("intent", "").lower()
                intent_map = {
                    "computer_control": Intent.COMPUTER_CONTROL,
                    "coding": Intent.CODING,
                    "research": Intent.RESEARCH,
                    "planning": Intent.PLANNING,
                    "verification": Intent.VERIFICATION,
                    "conversation": Intent.CONVERSATION,
                    "greeting": Intent.GREETING,
                }
                intent = intent_map.get(intent_str, Intent.CONVERSATION)

                return RoutingDecision(
                    selected_brain=llm_result.get("selected_brain", previous_decision.selected_brain),
                    confidence=min(llm_result.get("confidence", 0.5), 0.9),
                    best_score=llm_result.get("best_score", 0.5),
                    second_best_score=llm_result.get("second_best_score", 0.3),
                    score_margin=llm_result.get("score_margin", 0.2),
                    matched_capabilities=previous_decision.matched_capabilities,
                    required_tools=previous_decision.required_tools,
                    intent=intent,
                    complexity=Complexity[llm_result.get("complexity", "MODERATE").upper()],
                    workflow_required=llm_result.get("multi_agent", False),
                    reason=f"LLM fallback: {llm_result.get('reason', 'LLM classification')}",
                    ambiguity=llm_result.get("ambiguous", False),
                    candidate_agents=llm_result.get("candidates", previous_decision.candidate_agents),
                    needs_llm_classification=True,
                    classifier_source="llm_fallback",
                    routing_latency_ms=latency + llm_result.get("llm_latency_ms", 0),
                )

        except Exception as exc:
            logger.warning("LLM classifier failed: %s", exc)

        return previous_decision

    def get_alternative_brains(self, primary: str) -> List[Tuple[str, float]]:
        """Get fallback brain options if primary is unavailable."""
        if primary not in self._capability_registry:
            return []

        primary_caps = self._capability_registry[primary]
        alternatives: List[Tuple[str, float]] = []

        for brain_type, caps in self._capability_registry.items():
            if brain_type == primary:
                continue
            shared_intents = primary_caps.primary_intents & caps.primary_intents
            if shared_intents:
                alternatives.append((brain_type, 0.7))

        alternatives.sort(key=lambda x: x[1], reverse=True)
        return alternatives[:3]


__all__ = [
    "Intent",
    "Complexity",
    "RiskLevel",
    "BrainCapability",
    "BrainCapabilities",
    "BrainCapabilityRegistry",
    "TaskRequirements",
    "RoutingDecision",
    "RoutingScore",
    "CapabilityBasedRouter",
    "AmbiguousTaskError",
]
