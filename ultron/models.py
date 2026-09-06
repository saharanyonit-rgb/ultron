"""Strongly-typed data models for the JARVIS runtime pipeline.

These models carry structured information through the system so every layer
can inspect, log, and reason about what happened without relying on raw
strings or dicts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Runtime Context ────────────────────────────────────────────────

@dataclass
class RuntimeContext:
    """Carries request-scoped state through the entire pipeline."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    route_type: Optional[str] = None
    route_target: Optional[str] = None
    route_confidence: float = 0.0


# ── Planning ───────────────────────────────────────────────────────

class PlanStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step inside an execution plan."""

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional["ExecutionResult"] = None


@dataclass
class Plan:
    """An ordered sequence of steps the Brain intends to execute."""

    steps: List[PlanStep] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""

    @property
    def is_empty(self) -> bool:
        return len(self.steps) == 0

    def pending_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.PENDING]


# ── Execution ──────────────────────────────────────────────────────

class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"


@dataclass
class ExecutionResult:
    """Structured outcome of a single tool execution."""

    tool_name: str
    status: ExecutionStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)


# ── Verification ───────────────────────────────────────────────────

class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationResult:
    """Outcome of verifying an ExecutionResult."""

    execution_result: ExecutionResult
    status: VerificationStatus
    checks: Dict[str, bool] = field(default_factory=dict)
    message: str = ""


# ── Error ──────────────────────────────────────────────────────────

@dataclass
class ErrorResult:
    """Structured error information returned instead of raising exceptions."""

    error_type: str
    message: str
    details: Optional[str] = None
    recoverable: bool = True

    @classmethod
    def from_exception(cls, exc: Exception, recoverable: bool = True) -> "ErrorResult":
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            recoverable=recoverable,
        )


# ── Phase 3: Memory Records ──────────────────────────────────────

class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    FACT = "fact"
    TASK = "task"
    CODE = "code"
    RESEARCH = "research"
    NOTE = "note"


@dataclass
class MemoryRecord:
    """A single memory record with metadata for semantic retrieval."""

    content: str
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: str = ""
    session_id: Optional[str] = None
    role: str = "user"
    record_type: MemoryType = MemoryType.CONVERSATION
    importance: float = 0.5
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)


# ── Phase 3: Multi-step Planning ─────────────────────────────────

class PlanStepPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MultiStepPlanStep:
    """Extended plan step with dependencies and retry support."""

    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    objective: str = ""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional["ExecutionResult"] = None
    retry_count: int = 0
    max_retries: int = 3
    priority: PlanStepPriority = PlanStepPriority.NORMAL
    verification_state: Optional["VerificationResult"] = None

    @property
    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        return self.status == PlanStepStatus.PENDING and not self.dependencies

    @property
    def can_retry(self) -> bool:
        """Check if this step can be retried."""
        return self.status == PlanStepStatus.FAILED and self.retry_count < self.max_retries


@dataclass
class MultiStepPlan:
    """A plan with dependency management and retry support."""

    steps: List[MultiStepPlanStep] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    max_steps: int = 20

    @property
    def is_empty(self) -> bool:
        return len(self.steps) == 0

    def pending_steps(self) -> List[MultiStepPlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.PENDING]

    def ready_steps(self) -> List[MultiStepPlanStep]:
        """Return steps whose dependencies are all satisfied."""
        completed_ids = {s.step_id for s in self.steps if s.status == PlanStepStatus.SUCCEEDED}
        return [
            s for s in self.steps
            if s.status == PlanStepStatus.PENDING
            and all(dep in completed_ids for dep in s.dependencies)
        ]

    def failed_steps(self) -> List[MultiStepPlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.FAILED]

    def completed_steps(self) -> List[MultiStepPlanStep]:
        return [s for s in self.steps if s.status == PlanStepStatus.SUCCEEDED]

    def has_cycle(self) -> bool:
        """Detect dependency cycles using DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        dep_map = {s.step_id: s.dependencies for s in self.steps}

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for dep in dep_map.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for step in self.steps:
            if step.step_id not in visited:
                if dfs(step.step_id):
                    return True
        return False


__all__ = [
    "RuntimeContext",
    "PlanStep",
    "PlanStepStatus",
    "Plan",
    "ExecutionResult",
    "ExecutionStatus",
    "VerificationResult",
    "VerificationStatus",
    "ErrorResult",
    "MemoryType",
    "MemoryRecord",
    "PlanStepPriority",
    "MultiStepPlanStep",
    "MultiStepPlan",
]
