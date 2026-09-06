"""Autonomous Decision Loop for JARVIS Phase 5.

The core execution loop where LLM agents drive tool selection,
execution, result interpretation, and error handling.

Architecture:
    Task
        ↓
    Autonomous Executor
        ↓
    LLM Agent (reasoning loop)
        ↓
    Tool Selection → Security Boundary → Execution
        ↓
    Result Interpretation → Decision
        ↓
    CONTINUE / COMPLETE / RETRY / FAIL
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultron.agents.llm_agent import AgentDecisionType, AgentTrace, LLMAgent
from ultron.audit import AuditEvent, AuditLogger, EventType
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.task import Task, TaskStatus
from ultron.tools import Tool, ToolExecutor, ToolExecutionResult, ToolExecutionStatus

logger = logging.getLogger("ultron.autonomous")


class AutonomousState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AutonomousConfig:
    """Configuration for the autonomous executor."""
    max_iterations_per_task: int = 10
    max_tool_calls_per_task: int = 20
    task_timeout_seconds: int = 120


@dataclass
class TaskExecutionRecord:
    """Record of a single task's autonomous execution."""
    task_id: str = ""
    agent_name: str = ""
    iterations: int = 0
    tool_calls: int = 0
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    final_answer: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls,
            "decisions_count": len(self.decisions),
            "final_answer": self.final_answer,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class AutonomousExecutor:
    """Executes tasks using LLM-driven agent reasoning.

    Replaces the simple tool-dispatch loop in the orchestrator with
    an autonomous decision loop where the agent:
    1. Understands the task
    2. Selects appropriate tools
    3. Executes through the security boundary
    4. Interprets results
    5. Decides next action (continue, complete, retry, fail)
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        tool_executor: ToolExecutor,
        audit_logger: Optional[AuditLogger] = None,
        config: Optional[AutonomousConfig] = None,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._tool_executor = tool_executor
        self._audit = audit_logger or AuditLogger()
        self._config = config or AutonomousConfig()
        self._state = AutonomousState.IDLE
        self._records: Dict[str, TaskExecutionRecord] = {}

    @property
    def state(self) -> AutonomousState:
        return self._state

    def get_record(self, task_id: str) -> Optional[TaskExecutionRecord]:
        return self._records.get(task_id)

    def execute_task(
        self,
        task: Task,
        goal_context: Optional[str] = None,
        previous_results: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Execute a single task using the autonomous decision loop.

        Returns an ExecutionResult with the task's outcome.
        """
        record = TaskExecutionRecord(
            task_id=task.id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[task.id] = record
        self._state = AutonomousState.RUNNING

        # Build agent with tool executor for security enforcement
        agent = LLMAgent(
            provider=self._provider,
            tools=self._tools,
            max_iterations=self._config.max_iterations_per_task,
            tool_executor=self._tool_executor,
        )
        record.agent_name = agent.spec.name

        # Build context
        context = {}
        if goal_context:
            context["goal"] = goal_context
        if previous_results:
            context["previous_results"] = previous_results

        # Build the task prompt
        task_prompt = self._build_task_prompt(task, goal_context)

        try:
            trace = agent.run_with_trace(task_prompt, context)

            # Record trace info
            record.iterations = trace.iterations
            record.tool_calls = trace.tool_calls_made
            record.decisions = [d.to_dict() for d in trace.decisions]
            record.final_answer = trace.final_answer

            # Map trace to execution result
            if trace.error:
                record.status = "failed"
                record.error = trace.error
                record.completed_at = datetime.now(timezone.utc).isoformat()
                self._state = AutonomousState.IDLE
                return ExecutionResult(
                    tool_name=task.assigned_agent or "autonomous",
                    status=ExecutionStatus.FAILED,
                    output={"trace": trace.to_dict()},
                    error=trace.error,
                )

            if trace.completed:
                record.status = "completed"
                record.completed_at = datetime.now(timezone.utc).isoformat()
                self._state = AutonomousState.IDLE

                # Parse output from final answer
                output = self._parse_task_output(trace.final_answer or "")
                return ExecutionResult(
                    tool_name=task.assigned_agent or "autonomous",
                    status=ExecutionStatus.SUCCESS,
                    output=output,
                )
            else:
                record.status = "completed"
                record.completed_at = datetime.now(timezone.utc).isoformat()
                self._state = AutonomousState.IDLE

                return ExecutionResult(
                    tool_name=task.assigned_agent or "autonomous",
                    status=ExecutionStatus.SUCCESS,
                    output={"answer": trace.final_answer or ""},
                )

        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            self._state = AutonomousState.IDLE
            logger.error("Autonomous execution failed for task %s: %s", task.id, exc)
            return ExecutionResult(
                tool_name=task.assigned_agent or "autonomous",
                status=ExecutionStatus.FAILED,
                output={"error": str(exc)},
                error=str(exc),
            )

    def execute_tool_directly(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute a tool directly through the security boundary.

        Used when the agent needs to bypass the LLM and call a tool
        directly (e.g., for system operations).
        """
        self._audit.log(AuditEvent(
            event_type=EventType.TOOL_REQUESTED,
            request_id=str(uuid.uuid4())[:12],
            tool_name=tool_name,
            metadata={"arguments": arguments, "source": "autonomous_direct"},
        ))

        result = self._tool_executor.execute(tool_name, arguments)

        self._audit.log(AuditEvent(
            event_type=EventType.TOOL_RESULT,
            request_id=str(uuid.uuid4())[:12],
            tool_name=tool_name,
            success=result.status == ToolExecutionStatus.SUCCESS,
            metadata={"status": result.status.value},
        ))

        return result

    def _build_task_prompt(self, task: Task, goal_context: Optional[str] = None) -> str:
        """Build a detailed prompt for the agent to execute a task."""
        parts = [f"Task: {task.description}"]

        if task.objective:
            parts.append(f"Objective: {task.objective}")

        if goal_context:
            parts.append(f"Goal context: {goal_context}")

        if task.required_tools:
            parts.append(f"Available tools for this task: {', '.join(task.required_tools)}")

        if task.verification_criteria:
            parts.append(f"Verification criteria: {'; '.join(task.verification_criteria)}")

        if task.input_data:
            parts.append(f"Input data: {json.dumps(task.input_data, default=str)[:500]}")

        return "\n".join(parts)

    def _parse_task_output(self, answer: str) -> Dict[str, Any]:
        """Parse the agent's final answer into structured output."""
        # Try to parse as JSON
        cleaned = answer.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

        return {"answer": answer}


__all__ = [
    "AutonomousState",
    "AutonomousConfig",
    "TaskExecutionRecord",
    "AutonomousExecutor",
]
