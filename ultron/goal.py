"""Goal Engine for JARVIS Phase 5: Autonomous Intelligence.

Converts user objectives into structured Goal objects that can be decomposed
into task graphs. The Goal Engine normalizes requests, identifies constraints,
success criteria, and determines whether complex planning is required.

The Goal model sits above Phase 4's planning layer and feeds into the
Task Graph and Orchestrator.
"""

from __future__ import annotations

import re
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.goal")


class GoalStatus(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class GoalComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class GoalPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SuccessCriteria:
    """A single success criterion for a goal."""

    description: str
    criterion_type: str = "output"  # output, state, file, custom
    expected_value: Optional[str] = None
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "criterion_type": self.criterion_type,
            "expected_value": self.expected_value,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SuccessCriteria":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GoalConstraint:
    """A constraint that limits how a goal can be achieved."""

    description: str
    constraint_type: str = "general"  # general, time, resource, security, capability
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "constraint_type": self.constraint_type,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalConstraint":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Goal:
    """A structured user objective for autonomous execution.

    Captures the user's intent in a machine-processable form that the
    Planner can decompose into a TaskGraph.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    description: str = ""
    original_request: str = ""
    status: GoalStatus = GoalStatus.CREATED
    complexity: GoalComplexity = GoalComplexity.SIMPLE
    priority: GoalPriority = GoalPriority.NORMAL

    success_criteria: List[SuccessCriteria] = field(default_factory=list)
    constraints: List[GoalConstraint] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)

    required_capabilities: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)

    llm_reasoning: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "original_request": self.original_request,
            "status": self.status.value,
            "complexity": self.complexity.value,
            "priority": self.priority.value,
            "success_criteria": [c.to_dict() for c in self.success_criteria],
            "constraints": [c.to_dict() for c in self.constraints],
            "expected_outputs": self.expected_outputs,
            "required_capabilities": self.required_capabilities,
            "required_tools": self.required_tools,
            "llm_reasoning": self.llm_reasoning,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        success_criteria = [SuccessCriteria.from_dict(c) for c in data.get("success_criteria", [])]
        constraints = [GoalConstraint.from_dict(c) for c in data.get("constraints", [])]
        return cls(
            id=data.get("id", str(uuid.uuid4())[:12]),
            description=data.get("description", ""),
            original_request=data.get("original_request", ""),
            status=GoalStatus(data.get("status", "created")),
            complexity=GoalComplexity(data.get("complexity", "simple")),
            priority=GoalPriority(data.get("priority", "normal")),
            success_criteria=success_criteria,
            constraints=constraints,
            expected_outputs=data.get("expected_outputs", []),
            required_capabilities=data.get("required_capabilities", []),
            required_tools=data.get("required_tools", []),
            llm_reasoning=data.get("llm_reasoning"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            completed_at=data.get("completed_at"),
        )

    @property
    def needs_planning(self) -> bool:
        """Determine if this goal requires multi-step planning."""
        return self.complexity in (GoalComplexity.MODERATE, GoalComplexity.COMPLEX)

    def update_status(self, status: GoalStatus) -> None:
        self.status = status
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.CANCELLED):
            self.completed_at = self.updated_at


# ── Keywords for complexity detection ──────────────────────────────

COMPLEX_KEYWORDS = {
    "and then", "after that", "finally", "then verify", "then check",
    "then confirm", "and verify", "and check", "analyze and",
    "research and", "create and", "write and", "build and",
    "multiple", "several", "series of", "step by step",
    "end to end", "full workflow", "entire process",
}

MODERATE_KEYWORDS = {
    "create", "write", "generate", "analyze", "compare",
    "search", "find", "research", "verify", "check",
    "validate", "test", "build", "deploy", "configure",
    "update", "modify", "refactor", "review",
}

SIMPLE_INDICATORS = {
    "what is", "what's", "how do", "how to", "tell me",
    "show me", "get", "read", "open", "list", "what are",
}

# Capability keywords mapped to required capabilities
CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "research": ["research", "search", "find", "look up", "investigate", "analyze"],
    "coding": ["code", "code", "implement", "develop", "program", "script", "function", "class"],
    "writing": ["write", "draft", "create", "compose", "document", "report"],
    "filesystem": ["file", "directory", "folder", "create file", "read file", "delete", "move", "copy"],
    "browser": ["browse", "website", "url", "navigate", "web page", "internet"],
    "analysis": ["analyze", "compare", "evaluate", "assess", "review", "examine"],
}

# Tool keywords mapped to required tools
TOOL_KEYWORDS: Dict[str, List[str]] = {
    "create_file": ["create file", "create a file", "write file", "write a file", "make file", "save file"],
    "read_file": ["read file", "open file", "cat file", "view file"],
    "search_files": ["search files", "find files", "glob", "list files"],
    "delete_file": ["delete file", "remove file"],
    "open_url": ["open url", "open website", "browse to"],
    "open_app": ["open app", "launch app", "start app"],
    "take_screenshot": ["screenshot", "capture screen"],
    "get_system_info": ["system info", "cpu", "memory", "disk space"],
}


class GoalEngine:
    """Processes user requests into structured Goal objects.

    The Goal Engine:
    1. Normalizes the raw request
    2. Analyzes complexity
    3. Identifies constraints
    4. Extracts success criteria
    5. Determines required capabilities/tools
    6. Produces a structured Goal
    """

    def __init__(
        self,
        max_plan_steps: int = 20,
    ) -> None:
        self._max_plan_steps = max_plan_steps

    def create_goal(self, user_request: str) -> Goal:
        """Convert a user request into a structured Goal."""
        if not user_request or not isinstance(user_request, str):
            return Goal(
                description="Invalid request",
                original_request=str(user_request),
                status=GoalStatus.BLOCKED,
                metadata={"error": "Empty or invalid request"},
            )

        normalized = user_request.strip()
        if not normalized:
            return Goal(
                description="Empty request",
                original_request=user_request,
                status=GoalStatus.BLOCKED,
                metadata={"error": "Whitespace-only request"},
            )

        complexity = self._assess_complexity(normalized)
        priority = self._assess_priority(normalized)
        capabilities = self._detect_capabilities(normalized)
        tools = self._detect_tools(normalized)
        criteria = self._extract_success_criteria(normalized)
        constraints = self._extract_constraints(normalized)
        expected = self._extract_expected_outputs(normalized)
        description = self._generate_description(normalized)

        goal = Goal(
            description=description,
            original_request=normalized,
            complexity=complexity,
            priority=priority,
            required_capabilities=capabilities,
            required_tools=tools,
            success_criteria=criteria,
            constraints=constraints,
            expected_outputs=expected,
            metadata={
                "input_length": len(normalized),
                "word_count": len(normalized.split()),
            },
        )

        logger.info(
            "Goal created [id=%s, complexity=%s, capabilities=%s, tools=%s]",
            goal.id,
            goal.complexity.value,
            goal.required_capabilities,
            goal.required_tools,
        )

        return goal

    def _assess_complexity(self, text: str) -> GoalComplexity:
        """Determine goal complexity from the request text."""
        lower = text.lower()

        complex_score = sum(1 for kw in COMPLEX_KEYWORDS if kw in lower)
        moderate_score = sum(1 for kw in MODERATE_KEYWORDS if kw in lower)
        simple_score = sum(1 for kw in SIMPLE_INDICATORS if kw in lower)

        word_count = len(text.split())

        if complex_score >= 2 or (complex_score >= 1 and word_count > 30):
            return GoalComplexity.COMPLEX
        if moderate_score >= 2 or (moderate_score >= 1 and word_count > 15):
            return GoalComplexity.MODERATE
        if simple_score >= 1 and word_count <= 15:
            return GoalComplexity.SIMPLE

        if word_count > 40:
            return GoalComplexity.COMPLEX
        if word_count > 20:
            return GoalComplexity.MODERATE

        return GoalComplexity.SIMPLE

    def _assess_priority(self, text: str) -> GoalPriority:
        """Determine goal priority from the request text."""
        lower = text.lower()

        if any(w in lower for w in ["low priority", "no rush", "when you can", "eventually"]):
            return GoalPriority.LOW
        if any(w in lower for w in ["urgent", "asap", "immediately", "critical", "emergency"]):
            return GoalPriority.CRITICAL
        if any(w in lower for w in ["important", "high priority", "need now"]):
            return GoalPriority.HIGH

        return GoalPriority.NORMAL

    def _detect_capabilities(self, text: str) -> List[str]:
        """Detect which agent capabilities are required."""
        lower = text.lower()
        caps = []
        for cap, keywords in CAPABILITY_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                caps.append(cap)
        return list(set(caps))

    def _detect_tools(self, text: str) -> List[str]:
        """Detect which tools are likely needed."""
        lower = text.lower()
        tools = []
        for tool, keywords in TOOL_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                tools.append(tool)
        return list(set(tools))

    def _extract_success_criteria(self, text: str) -> List[SuccessCriteria]:
        """Extract success criteria from the request."""
        criteria = []
        lower = text.lower()

        if any(w in lower for w in ["verify", "check", "confirm", "ensure"]):
            criteria.append(SuccessCriteria(
                description="Results verified and confirmed",
                criterion_type="verification",
            ))

        if any(w in lower for w in ["file", "create file", "write file"]):
            criteria.append(SuccessCriteria(
                description="File operations completed successfully",
                criterion_type="file",
            ))

        if any(w in lower for w in ["report", "summary", "summary"]):
            criteria.append(SuccessCriteria(
                description="Report or summary generated",
                criterion_type="output",
            ))

        if any(w in lower for w in ["test", "validate", "verify"]):
            criteria.append(SuccessCriteria(
                description="Tests or validation passed",
                criterion_type="verification",
            ))

        if not criteria:
            criteria.append(SuccessCriteria(
                description="Goal objective achieved",
                criterion_type="output",
            ))

        return criteria

    def _extract_constraints(self, text: str) -> List[GoalConstraint]:
        """Extract constraints from the request."""
        constraints = []
        lower = text.lower()

        if any(w in lower for w in ["don't", "do not", "never", "must not"]):
            constraints.append(GoalConstraint(
                description="Negative constraint detected in request",
                constraint_type="general",
            ))

        if any(w in lower for w in ["only", "just", "simply"]):
            constraints.append(GoalConstraint(
                description="Scope limitation detected",
                constraint_type="scope",
            ))

        if any(w in lower for w in ["quick", "fast", "immediately"]):
            constraints.append(GoalConstraint(
                description="Time constraint: quick execution preferred",
                constraint_type="time",
            ))

        return constraints

    def _extract_expected_outputs(self, text: str) -> List[str]:
        """Extract expected output descriptions."""
        outputs = []
        lower = text.lower()

        if any(w in lower for w in ["file", "create file", "write file"]):
            outputs.append("Created file(s)")

        if any(w in lower for w in ["report", "summary", "document"]):
            outputs.append("Report or summary")

        if any(w in lower for w in ["list", "show", "display"]):
            outputs.append("Listed information")

        if any(w in lower for w in ["answer", "explain", "describe"]):
            outputs.append("Explanation or answer")

        return outputs

    def _generate_description(self, text: str) -> str:
        """Generate a concise description from the request."""
        if len(text) <= 100:
            return text
        return text[:97] + "..."


__all__ = [
    "GoalStatus",
    "GoalComplexity",
    "GoalPriority",
    "SuccessCriteria",
    "GoalConstraint",
    "Goal",
    "GoalEngine",
]
