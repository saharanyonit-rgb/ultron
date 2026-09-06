"""Execution Orchestrator for JARVIS Phase 5: Autonomous Intelligence.

Central orchestration loop that coordinates:
1. Goal Engine → Goal
2. GoalPlanner → TaskGraph
3. AgentManager → agent assignment
4. Task execution via existing Phase 4 tools
5. Verification Engine → verification
6. Recovery → retry/replan
7. Context Management → bounded context
8. Persistence → state survival
9. Human approval gates → risk/policy integration
10. Response Engine → final result

The orchestrator sits ABOVE Phase 4 and delegates all real-world
actions through the existing security/permission/audit layer.
"""

from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ultron.agent_manager import AgentManager, AgentMessage, MessageType
from ultron.audit import AuditLogger, AuditEvent, EventType
from ultron.autonomous import AutonomousExecutor, AutonomousConfig
from ultron.context import (
    AgentContext,
    ContextManager,
    ExecutionContext,
    GoalContext,
    TaskContext,
)
from ultron.execution_state import ExecutionStateStore, TaskState, TaskStatus as PersistTaskStatus
from ultron.goal import Goal, GoalEngine, GoalStatus
from ultron.llm.base import LLMProvider
from ultron.llm_goal import LLMGoalEngine
from ultron.llm_planner import LLMGoalPlanner
from ultron.models import ExecutionResult, ExecutionStatus
from ultron.planner_v5 import GoalPlanner, PlanningError
from ultron.policy import PolicyEngine
from ultron.recovery import RecoveryEngine, RecoveryAction
from ultron.response import GoalResult, ResponseEngine, ResponseOutcome
from ultron.risk import RiskClassifier
from ultron.status import StatusEvent, StatusReporter
from ultron.task import Task, TaskGraph, TaskPriority, TaskStatus
from ultron.tools import ToolExecutor, ToolExecutionResult, ToolExecutionStatus
from ultron.verification_v5 import (
    TaskVerificationResult,
    VerificationCheck,
    VerificationEngine,
)

from ultron.orchestrator_types import (
    OrchestratorConfig,
    OrchestratorResult,
    OrchestratorState,
)

logger = logging.getLogger("ultron.orchestrator")


def _default_brain_event_handler(event_type: str, data: Dict[str, Any]) -> None:
    """Default no-op brain event handler."""
    pass


class Orchestrator:
    """Central execution orchestrator for Phase 5 autonomous goals.

    Coordinates all Phase 5 components while delegating real-world
    actions through Phase 4's security/permission/audit layer.
    """

    def __init__(
        self,
        tool_executor: ToolExecutor,
        agent_manager: Optional[AgentManager] = None,
        config: Optional[OrchestratorConfig] = None,
        audit_logger: Optional[AuditLogger] = None,
        status_reporter: Optional[StatusReporter] = None,
        state_store: Optional[ExecutionStateStore] = None,
        policy_engine: Optional[PolicyEngine] = None,
        risk_classifier: Optional[RiskClassifier] = None,
        autonomous_executor: Optional[AutonomousExecutor] = None,
        llm_provider: Optional[LLMProvider] = None,
        goal_engine: Optional[Any] = None,
        planner: Optional[Any] = None,
        brain_orchestrator: Optional[Any] = None,
        brain_event_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._tool_executor = tool_executor
        self._agent_manager = agent_manager or AgentManager()
        self._brain_orchestrator = brain_orchestrator
        self._brain_event_handler = brain_event_handler or _default_brain_event_handler

        # Determine active LLM provider (explicit parameter or extracted from autonomous executor)
        provider = llm_provider or (
            getattr(autonomous_executor, "_provider", None) if autonomous_executor else None
        )

        # Wire Goal Engine: prefer explicit goal_engine, then LLMGoalEngine if provider available, else fallback GoalEngine
        if goal_engine is not None:
            self._goal_engine = goal_engine
        elif provider is not None:
            tool_names = [t.name for t in tool_executor.registry.list_tools()] if hasattr(tool_executor, "registry") and hasattr(getattr(tool_executor, "registry", None), "list_tools") else []
            self._goal_engine = LLMGoalEngine(provider=provider, available_tools=tool_names)
        else:
            self._goal_engine = GoalEngine()

        # Wire Goal Planner: prefer explicit planner, then LLMGoalPlanner if provider available, else fallback GoalPlanner
        if planner is not None:
            self._planner = planner
        elif provider is not None:
            tool_names = [t.name for t in tool_executor.registry.list_tools()] if hasattr(tool_executor, "registry") and hasattr(getattr(tool_executor, "registry", None), "list_tools") else []
            self._planner = LLMGoalPlanner(provider=provider, available_tools=tool_names)
        else:
            self._planner = GoalPlanner()

        self._verification_engine = VerificationEngine()
        self._response_engine = ResponseEngine()
        self._recovery_engine = RecoveryEngine(max_retries=self._config.max_retries)
        self._context_manager = ContextManager()
        self._audit = audit_logger or AuditLogger()
        self._status = status_reporter or StatusReporter()
        self._state_store = state_store
        self._policy_engine = policy_engine
        self._risk_classifier = risk_classifier or RiskClassifier()
        self._autonomous_executor = autonomous_executor

        self._state = OrchestratorState.IDLE
        self._current_goal: Optional[Goal] = None
        self._current_graph: Optional[TaskGraph] = None
        self._execution_id = str(uuid.uuid4())[:12]
        self._events: List[Dict[str, Any]] = []
        # Lock protecting shared mutable state during parallel execution.
        # Serializes mutations to Task, TaskGraph, ContextManager,
        # StatusReporter, and AgentManager while keeping actual tool
        # execution (the expensive part) fully concurrent.
        self._lock = threading.Lock()

    @property
    def state(self) -> OrchestratorState:
        return self._state

    @property
    def current_goal(self) -> Optional[Goal]:
        return self._current_goal

    @property
    def current_graph(self) -> Optional[TaskGraph]:
        return self._current_graph

    @property
    def brain_orchestrator(self) -> Optional[Any]:
        return self._brain_orchestrator

    def _should_use_brain(self, user_request: str) -> bool:
        """Determine if brain orchestration should be used for this request.

        Uses brain routing when:
        - BrainOrchestrator is available
        - Request is complex (multi-step, planning keywords)
        - Request matches specialized brain patterns (research, coding, computer)
        """
        if not self._brain_orchestrator:
            return False

        text = user_request.lower().strip()

        # Brain orchestration indicators
        complex_indicators = [
            " and then", " first ", " after that", " next ",
            " multiple ", " steps", " workflow", " plan",
            " research ", " analyze", " compare",
        ]

        specialized_indicators = [
            "research", "analyze", "investigate",
            "code", "fix", "bug", "implement", "refactor",
            "open chrome", "open app", "browser", "navigate",
            "verify", "check result", "confirm",
        ]

        for indicator in complex_indicators:
            if indicator in text:
                return True

        for indicator in specialized_indicators:
            if indicator in text:
                return True

        return False

    def execute_goal(self, user_request: str) -> OrchestratorResult:
        """Execute a user request as an autonomous goal.

        Full lifecycle: goal → plan → execute → verify → respond.
        Uses brain orchestration for complex/specialized requests when available.
        """
        self._events = []
        self._emit("EXECUTION_START", {"request": user_request[:100]})

        try:
            # Check if we should use brain orchestration for this request
            if self._should_use_brain(user_request):
                return self._execute_via_brain(user_request)

            goal = self._create_goal(user_request)
            if goal.status == GoalStatus.BLOCKED:
                return self._blocked_result(goal)

            graph = self._create_plan(goal)
            self._persist_state(goal, graph)

            result = self._execute_graph(goal, graph)

            self._state = OrchestratorState.COMPLETED
            self._emit("EXECUTION_COMPLETE", {"outcome": result.goal_result.outcome.value})

            return result

        except Exception as exc:
            self._state = OrchestratorState.FAILED
            logger.error("Orchestration failed: %s", exc)
            self._emit("EXECUTION_FAILED", {"error": str(exc)})

            goal = goal if 'goal' in dir() else Goal(
                description=user_request,
                original_request=user_request,
                status=GoalStatus.FAILED,
            )
            result = self._response_engine.generate(goal, TaskGraph())
            return OrchestratorResult(
                goal_result=result,
                state=OrchestratorState.FAILED,
                events=self._events,
            )

    def _execute_via_brain(self, user_request: str) -> OrchestratorResult:
        """Execute a request via BrainOrchestrator for specialized processing.

        This path is used for complex/specialized requests that benefit from
        dedicated brain processing (research, coding, planning, etc.).
        """
        from ultron.brains.orchestrator import BrainContext

        logger.info("Routing request to BrainOrchestrator: %s", user_request[:100])

        try:
            brain_context = BrainContext(
                goal=user_request,
                metadata={"source": "orchestrator"},
            )

            # Emit brain routing event
            self._emit("BRAIN_ROUTING", {"request": user_request[:100]})

            # Execute via brain orchestrator
            result = self._brain_orchestrator.execute(user_request, brain_context)

            # Convert BrainOrchestrationResult to OrchestratorResult
            if result.success:
                self._state = OrchestratorState.COMPLETED

                # Create a simple goal result from brain output
                goal = Goal(
                    description=user_request,
                    original_request=user_request,
                    status=GoalStatus.COMPLETED,
                )

                goal_result = self._response_engine.generate(goal, TaskGraph())

                # Update with brain output
                goal_result.summary = str(result.output)[:1000] if result.output else "Brain execution completed"

                return OrchestratorResult(
                    goal_result=goal_result,
                    state=OrchestratorState.COMPLETED,
                    events=self._events,
                )
            else:
                self._state = OrchestratorState.FAILED

                goal = Goal(
                    description=user_request,
                    original_request=user_request,
                    status=GoalStatus.FAILED,
                )

                goal_result = self._response_engine.generate(goal, TaskGraph())
                goal_result.summary = result.error or "Brain execution failed"

                return OrchestratorResult(
                    goal_result=goal_result,
                    state=OrchestratorState.FAILED,
                    events=self._events,
                )

        except Exception as exc:
            logger.error("Brain orchestration failed: %s", exc)
            self._state = OrchestratorState.FAILED
            self._emit("BRAIN_ERROR", {"error": str(exc)})

            goal = Goal(
                description=user_request,
                original_request=user_request,
                status=GoalStatus.FAILED,
            )
            result = self._response_engine.generate(goal, TaskGraph())
            return OrchestratorResult(
                goal_result=result,
                state=OrchestratorState.FAILED,
                events=self._events,
            )

    def resume_goal(self, goal: Goal, graph: TaskGraph) -> OrchestratorResult:
        """Resume an interrupted goal from persisted state."""
        self._current_goal = goal
        self._current_graph = graph
        self._context_manager.set_goal_context(GoalContext(
            goal_id=goal.id,
            goal_description=goal.description,
            original_request=goal.original_request,
        ))

        incomplete_tasks = [
            t for t in graph.tasks
            if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.READY)
        ]

        for task in incomplete_tasks:
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.PENDING
                task.retry_count += 1

        return self._execute_graph(goal, graph)

    def _create_goal(self, user_request: str) -> Goal:
        """Create a Goal from user request."""
        self._state = OrchestratorState.PLANNING
        self._status.planning("orchestrator")

        goal = self._goal_engine.create_goal(user_request)
        self._current_goal = goal

        self._context_manager.set_goal_context(GoalContext(
            goal_id=goal.id,
            goal_description=goal.description,
            original_request=goal.original_request,
            success_criteria=[c.description for c in goal.success_criteria],
            constraints=[c.description for c in goal.constraints],
            expected_outputs=goal.expected_outputs,
        ))

        self._audit.log(AuditEvent(
            event_type=EventType.REQUEST_RECEIVED,
            request_id=self._execution_id,
            task_id=goal.id,
            metadata={"goal_description": goal.description, "complexity": goal.complexity.value},
        ))

        self._emit("GOAL_CREATED", {"goal_id": goal.id, "complexity": goal.complexity.value})

        return goal

    def _create_plan(self, goal: Goal) -> TaskGraph:
        """Create a TaskGraph from a Goal."""
        graph = self._planner.plan(goal)
        self._current_graph = graph

        self._audit.log(AuditEvent(
            event_type=EventType.PLAN_CREATED,
            request_id=self._execution_id,
            task_id=goal.id,
            metadata={"task_count": graph.task_count, "description": graph.description},
        ))

        self._status.plan_created(goal.id, graph.task_count)
        self._emit("PLAN_CREATED", {
            "goal_id": goal.id,
            "task_count": graph.task_count,
            "parallel_groups": len(graph.get_parallel_groups()),
        })

        return graph

    def _execute_graph(self, goal: Goal, graph: TaskGraph) -> OrchestratorResult:
        """Execute the task graph, handling parallelism, verification, and recovery."""
        self._state = OrchestratorState.EXECUTING
        max_iterations = graph.task_count * 3
        iteration = 0

        while not graph.is_complete and iteration < max_iterations:
            iteration += 1
            ready = graph.ready_tasks()

            if not ready:
                if graph.has_failures:
                    self._handle_graph_failure(goal, graph)
                break

            if self._config.enable_parallel_execution and len(ready) > 1:
                self._execute_parallel(goal, graph, ready)
            else:
                for task in ready:
                    self._execute_single_task(goal, graph, task)

        verification_results = {}
        if self._config.enable_verification:
            self._status.verifying(goal.id, "Starting verification...")
            verification_results = self._verify_completed_tasks(goal, graph)

        outputs = self._collect_outputs(graph)
        limitations = self._detect_limitations(graph)

        goal_result = self._response_engine.generate(
            goal, graph, verification_results, outputs, limitations,
        )

        self._audit.log_final_response(
            self._execution_id,
            goal_result.outcome == ResponseOutcome.SUCCESS,
            len(goal_result.summary),
        )

        return OrchestratorResult(
            goal_result=goal_result,
            state=self._state,
            events=self._events,
        )

    def _execute_single_task(self, goal: Goal, graph: TaskGraph, task: Task) -> None:
        """Execute a single task."""
        task.mark_running()
        self._status.step_started(goal.id, task.id, task.description, graph.progress)

        self._audit.log(AuditEvent(
            event_type=EventType.STEP_STARTED,
            request_id=self._execution_id,
            task_id=goal.id,
            step_id=task.id,
            metadata={"description": task.description, "agent": task.assigned_agent},
        ))

        agent = self._agent_manager.select_agent(task.required_capabilities)
        if agent:
            task.assigned_agent = agent.spec.name
            self._agent_manager.mark_busy(agent.spec.name, task.id)
            self._status.agent_selected(goal.id, agent.spec.name)

        result = self._execute_task_tools(task)

        if result.status == ExecutionStatus.SUCCESS:
            task.mark_completed({"tool_result": result.output})
            self._on_task_completed(goal, graph, task)
            if agent:
                self._agent_manager.mark_available(agent.spec.name, True)
        else:
            self._handle_task_failure(goal, graph, task, result.error or "Unknown error")
            if agent:
                self._agent_manager.mark_available(agent.spec.name, False)

        self._status.step_completed(goal.id, task.id, graph.progress)

    def _execute_parallel(self, goal: Goal, graph: TaskGraph, tasks: List[Task]) -> None:
        """Execute multiple independent tasks in parallel.

        Tool execution runs concurrently across threads, but all shared
        state mutations (Task status, TaskGraph, ContextManager,
        StatusReporter, AgentManager) are serialized via ``self._lock``
        to prevent race conditions.
        """
        max_workers = min(len(tasks), self._config.max_concurrent_tasks)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for task in tasks:
                with self._lock:
                    task.mark_running()
                    self._status.step_started(goal.id, task.id, task.description, graph.progress)
                future = executor.submit(self._execute_task_tools, task)
                futures[future] = task

            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    with self._lock:
                        if result.status == ExecutionStatus.SUCCESS:
                            task.mark_completed({"tool_result": result.output})
                            self._on_task_completed(goal, graph, task)
                        else:
                            self._handle_task_failure(goal, graph, task, result.error or "Unknown error")
                except Exception as exc:
                    with self._lock:
                        self._handle_task_failure(goal, graph, task, str(exc))

                with self._lock:
                    self._status.step_completed(goal.id, task.id, graph.progress)

    def _execute_task_tools(self, task: Task) -> ExecutionResult:
        """Execute the tools for a task.

        When an AutonomousExecutor is available, delegates to it for
        LLM-driven agent reasoning. Otherwise falls back to direct
        tool dispatch through the security boundary.
        """
        # Use autonomous executor for LLM-driven execution when available
        if self._autonomous_executor:
            goal_context = (
                self._current_goal.description if self._current_goal else ""
            )
            previous = self._collect_outputs(self._current_graph) if self._current_graph else None
            return self._autonomous_executor.execute_task(
                task,
                goal_context=goal_context,
                previous_results=previous,
            )

        # Fallback: direct tool dispatch (original Phase 4 path)
        tool_name = task.required_tools[0] if task.required_tools else None
        if not tool_name:
            return ExecutionResult(
                tool_name="none",
                status=ExecutionStatus.SUCCESS,
                output={"message": "No tools required for this task"},
            )

        arguments = task.input_data.get("arguments", {})
        if "path" in task.input_data:
            arguments["path"] = task.input_data["path"]
        if "content" in task.input_data:
            arguments["content"] = task.input_data["content"]

        risk = self._risk_classifier.classify(tool_name, arguments)
        if self._policy_engine:
            allowed = self._policy_engine.request_permission(tool_name, risk, arguments)
            if not allowed:
                return ExecutionResult(
                    tool_name=tool_name,
                    status=ExecutionStatus.PERMISSION_DENIED,
                    output={"error": "Permission denied"},
                    error="Permission denied by policy engine",
                )

        exec_result = self._tool_executor.execute(tool_name, arguments)

        return ExecutionResult(
            tool_name=exec_result.tool_name,
            status=(
                ExecutionStatus.SUCCESS
                if exec_result.status == ToolExecutionStatus.SUCCESS
                else ExecutionStatus.FAILED
            ),
            output=exec_result.output,
            error=exec_result.error,
            arguments=exec_result.arguments,
        )

    def _on_task_completed(self, goal: Goal, graph: TaskGraph, task: Task) -> None:
        """Handle task completion: propagate to dependents, persist state."""
        self._audit.log(AuditEvent(
            event_type=EventType.STEP_COMPLETED,
            request_id=self._execution_id,
            task_id=goal.id,
            step_id=task.id,
            metadata={"duration": task.duration_seconds},
        ))

        newly_ready = graph.on_task_completed(task.id, task.output_data)

        self._context_manager.set_task_context(task.id, TaskContext(
            task_id=task.id,
            task_description=task.description,
            objective=task.objective,
            input_data=task.output_data,
        ))

        if self._state_store:
            self._persist_state(goal, graph)

    def _handle_task_failure(self, goal: Goal, graph: TaskGraph, task: Task, error: str) -> None:
        """Handle task failure with recovery decisions."""
        task.mark_failed(error)

        self._audit.log(AuditEvent(
            event_type=EventType.STEP_FAILED,
            request_id=self._execution_id,
            task_id=goal.id,
            step_id=task.id,
            success=False,
            error=error,
        ))

        self._status.step_failed(goal.id, task.id, error)

        decision = self._recovery_engine.decide_recovery(
            task,
            Exception(error),
            [task.output_data] if task.output_data else None,
        )

        self._audit.log_recovery(
            self._execution_id,
            decision.action.value,
            decision.reason,
        )

        if decision.action == RecoveryAction.RETRY and task.can_retry:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            self._status.retrying(goal.id, task.id)
            self._emit("TASK_RETRY", {
                "task_id": task.id,
                "retry": task.retry_count,
                "max_retries": task.max_retries,
            })
        elif decision.action == RecoveryAction.SKIP:
            graph.on_task_failed(task.id, error, propagate=False)
        else:
            blocked = graph.on_task_failed(task.id, error, propagate=True)
            self._emit("TASK_FAILED_BLOCKED", {
                "task_id": task.id,
                "blocked_tasks": blocked,
            })

    def _handle_graph_failure(self, goal: Goal, graph: TaskGraph) -> None:
        """Handle unrecoverable graph failure."""
        self._state = OrchestratorState.RECOVERING
        self._status.recovering(goal.id, "Analyzing failure and seeking alternative path")

        failed_tasks = graph.get_tasks_by_status(TaskStatus.FAILED)
        if failed_tasks:
            task = failed_tasks[0]
            try:
                self._status.replaning(goal.id, "Generating alternative execution path")
                new_graph = self._planner.replan(goal, graph, task.id)
                self._current_graph = new_graph
                self._emit("REPLAN", {"old_task": task.id, "new_task_count": new_graph.task_count})
            except PlanningError as exc:
                logger.error("Replanning failed: %s", exc)
                self._state = OrchestratorState.FAILED

    def _verify_completed_tasks(self, goal: Goal, graph: TaskGraph) -> Dict[str, bool]:
        """Verify all completed tasks."""
        results = {}
        verified_any = False

        for task in graph.get_tasks_by_status(TaskStatus.COMPLETED):
            if not task.verification_criteria:
                continue

            verified_any = True
            task.mark_running()
            self._status.verifying(goal.id, task.id)
            checks = self._verification_engine.build_checks_from_criteria(task.verification_criteria)

            exec_result = ExecutionResult(
                tool_name=task.assigned_agent or "task",
                status=ExecutionStatus.SUCCESS,
                output=task.output_data,
            )

            verification = self._verification_engine.verify_task(task.id, exec_result, checks)
            results[task.id] = verification.overall_passed

            self._status.verified(goal.id, task.id, verification.overall_passed)

            if verification.overall_passed:
                task.verification_state = "passed"
                task.status = TaskStatus.COMPLETED
            else:
                task.verification_state = "failed"
                task.status = TaskStatus.COMPLETED

            self._audit.log_verification(
                self._execution_id,
                task.id,
                verification.overall_passed,
                {r.check.description: r.passed for r in verification.check_results},
            )

        return results

    def _collect_outputs(self, graph: TaskGraph) -> Dict[str, Any]:
        """Collect important outputs from completed tasks."""
        outputs = {}
        for task in graph.get_tasks_by_status(TaskStatus.COMPLETED):
            if task.output_data:
                outputs[task.id] = {
                    "description": task.description,
                    "output": task.output_data,
                }
        return outputs

    def _detect_limitations(self, graph: TaskGraph) -> List[str]:
        """Detect execution limitations."""
        limitations = []

        failed = graph.get_tasks_by_status(TaskStatus.FAILED)
        if failed:
            limitations.append(f"{len(failed)} tasks failed")

        blocked = graph.get_tasks_by_status(TaskStatus.BLOCKED)
        if blocked:
            limitations.append(f"{len(blocked)} tasks blocked by failures")

        cancelled = graph.get_tasks_by_status(TaskStatus.CANCELLED)
        if cancelled:
            limitations.append(f"{len(cancelled)} tasks cancelled")

        return limitations

    def _persist_state(self, goal: Goal, graph: TaskGraph) -> None:
        """Persist execution state for recovery."""
        if not self._state_store:
            return

        task_state = TaskState(
            task_id=goal.id,
            description=goal.description,
            status=PersistTaskStatus.RUNNING,
        )

        for task in graph.tasks:
            step = __import__("ultron.execution_state", fromlist=["StepState"]).StepState(
                step_id=task.id,
                objective=task.description,
                status=task.status.value,
                result=task.output_data if task.output_data else None,
                error=task.error,
                retry_count=task.retry_count,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
            task_state.steps.append(step)

        if graph.is_complete:
            task_state.status = (
                PersistTaskStatus.COMPLETED if not graph.has_failures
                else PersistTaskStatus.FAILED
            )

        self._state_store.save_task(task_state)

    def _blocked_result(self, goal: Goal) -> OrchestratorResult:
        """Create a result for a blocked goal."""
        result = self._response_engine.generate(goal, TaskGraph())
        return OrchestratorResult(
            goal_result=result,
            state=OrchestratorState.FAILED,
            events=self._events,
        )

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an orchestration event."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_id": self._execution_id,
            **data,
        }
        self._events.append(event)
        logger.info("Event: %s %s", event_type, data)


__all__ = [
    "OrchestratorState",
    "OrchestratorConfig",
    "OrchestratorResult",
    "Orchestrator",
]
