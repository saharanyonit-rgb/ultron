"""Context Management for JARVIS Phase 5: Autonomous Intelligence.

Provides structured, bounded context for different execution layers:
- Global Goal Context: the overall objective and metadata
- Task Context: specific to a single task
- Agent Context: specific to an agent's execution
- Execution Context: runtime state and tool results
- Tool Result Context: specific tool execution results

Context is serializable and restorable for persistence.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.context")


@dataclass
class GoalContext:
    """Global context for the entire goal execution."""

    goal_id: str = ""
    goal_description: str = ""
    original_request: str = ""
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "original_request": self.original_request,
            "success_criteria": self.success_criteria,
            "constraints": self.constraints,
            "expected_outputs": self.expected_outputs,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TaskContext:
    """Context for a single task execution."""

    task_id: str = ""
    task_description: str = ""
    objective: str = ""
    assigned_agent: Optional[str] = None
    required_capabilities: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    dependencies_completed: Dict[str, Any] = field(default_factory=dict)
    verification_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "objective": self.objective,
            "assigned_agent": self.assigned_agent,
            "required_capabilities": self.required_capabilities,
            "required_tools": self.required_tools,
            "input_data": self.input_data,
            "dependencies_completed": self.dependencies_completed,
            "verification_criteria": self.verification_criteria,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentContext:
    """Context for an agent's execution session."""

    agent_name: str = ""
    capabilities: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    current_task_id: Optional[str] = None
    previous_results: List[Dict[str, Any]] = field(default_factory=list)
    max_iterations: int = 8
    iteration: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "capabilities": self.capabilities,
            "available_tools": self.available_tools,
            "current_task_id": self.current_task_id,
            "previous_results": self.previous_results,
            "max_iterations": self.max_iterations,
            "iteration": self.iteration,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ExecutionContext:
    """Runtime execution context with tool results and state."""

    request_id: str = ""
    task_id: str = ""
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_tool_result(self, tool_name: str, result: Dict[str, Any], success: bool) -> None:
        self.tool_results.append({
            "tool_name": tool_name,
            "result": result,
            "success": success,
        })

    def add_error(self, error: str) -> None:
        self.errors.append(error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "tool_results": self.tool_results,
            "errors": self.errors,
            "state": self.state,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ToolResultContext:
    """Context for a specific tool execution result."""

    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    output: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error: Optional[str] = None
    duration_ms: float = 0.0
    risk_level: str = ""
    permission_granted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "output": self.output,
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "risk_level": self.risk_level,
            "permission_granted": self.permission_granted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolResultContext":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ContextManager:
    """Manages layered context for autonomous execution.

    Prevents uncontrolled context growth by keeping contexts bounded
    and relevant to the current execution layer.
    """

    def __init__(self, max_history: int = 50) -> None:
        self._max_history = max_history
        self._goal_context: Optional[GoalContext] = None
        self._task_contexts: Dict[str, TaskContext] = {}
        self._agent_contexts: Dict[str, AgentContext] = {}
        self._execution_contexts: Dict[str, ExecutionContext] = {}
        self._tool_result_history: List[ToolResultContext] = []

    def set_goal_context(self, context: GoalContext) -> None:
        self._goal_context = context

    def get_goal_context(self) -> Optional[GoalContext]:
        return self._goal_context

    def set_task_context(self, task_id: str, context: TaskContext) -> None:
        self._task_contexts[task_id] = context

    def get_task_context(self, task_id: str) -> Optional[TaskContext]:
        return self._task_contexts.get(task_id)

    def set_agent_context(self, agent_name: str, context: AgentContext) -> None:
        self._agent_contexts[agent_name] = context

    def get_agent_context(self, agent_name: str) -> Optional[AgentContext]:
        return self._agent_contexts.get(agent_name)

    def set_execution_context(self, task_id: str, context: ExecutionContext) -> None:
        self._execution_contexts[task_id] = context

    def get_execution_context(self, task_id: str) -> Optional[ExecutionContext]:
        return self._execution_contexts.get(task_id)

    def add_tool_result(self, context: ToolResultContext) -> None:
        self._tool_result_history.append(context)
        if len(self._tool_result_history) > self._max_history:
            self._tool_result_history = self._tool_result_history[-self._max_history:]

    def get_tool_result_history(self, limit: int = 10) -> List[ToolResultContext]:
        return self._tool_result_history[-limit:]

    def build_agent_prompt_context(self, task_context: TaskContext) -> str:
        """Build a focused prompt context for an agent."""
        parts = []

        if self._goal_context:
            parts.append(f"Goal: {self._goal_context.goal_description}")

        parts.append(f"Task: {task_context.objective}")

        if task_context.dependencies_completed:
            parts.append("Completed dependencies:")
            for dep_id, dep_output in task_context.dependencies_completed.items():
                summary = str(dep_output)[:200]
                parts.append(f"  - {dep_id}: {summary}")

        if task_context.verification_criteria:
            parts.append(f"Verify: {'; '.join(task_context.verification_criteria)}")

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_context": self._goal_context.to_dict() if self._goal_context else None,
            "task_contexts": {k: v.to_dict() for k, v in self._task_contexts.items()},
            "agent_contexts": {k: v.to_dict() for k, v in self._agent_contexts.items()},
            "execution_contexts": {k: v.to_dict() for k, v in self._execution_contexts.items()},
            "tool_result_history": [t.to_dict() for t in self._tool_result_history[-self._max_history:]],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextManager":
        mgr = cls()
        if data.get("goal_context"):
            mgr._goal_context = GoalContext.from_dict(data["goal_context"])
        for k, v in data.get("task_contexts", {}).items():
            mgr._task_contexts[k] = TaskContext.from_dict(v)
        for k, v in data.get("agent_contexts", {}).items():
            mgr._agent_contexts[k] = AgentContext.from_dict(v)
        for k, v in data.get("execution_contexts", {}).items():
            mgr._execution_contexts[k] = ExecutionContext.from_dict(v)
        for v in data.get("tool_result_history", []):
            mgr._tool_result_history.append(ToolResultContext.from_dict(v))
        return mgr


__all__ = [
    "GoalContext",
    "TaskContext",
    "AgentContext",
    "ExecutionContext",
    "ToolResultContext",
    "ContextManager",
]
