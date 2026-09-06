"""Goal Planner for JARVIS Phase 5: Autonomous Intelligence.

Converts Goals into TaskGraphs by analyzing complexity, identifying required
work, decomposing into atomic tasks, and determining dependencies. The Planner
sits between the Goal Engine and the Execution Orchestrator.

Key design principle: simple requests should remain simple. The planner avoids
unnecessary decomposition.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ultron.goal import Goal, GoalComplexity
from ultron.task import Task, TaskGraph, TaskPriority, TaskStatus

logger = logging.getLogger("ultron.planner_v5")


class PlanningError(Exception):
    """Raised when planning fails."""


class GoalPlanner:
    """Converts Goals into executable TaskGraphs.

    Planning strategy:
    1. Simple goals → single task (no decomposition)
    2. Moderate goals → minimal decomposition
    3. Complex goals → full decomposition with dependencies
    """

    def __init__(self, max_tasks: int = 20) -> None:
        self._max_tasks = max_tasks

    def plan(self, goal: Goal) -> TaskGraph:
        """Create a TaskGraph from a Goal."""
        status_val = goal.status.value if hasattr(goal.status, "value") else str(goal.status)
        if status_val in ("blocked", "cancelled"):
            raise PlanningError(f"Cannot plan a goal in '{status_val}' state")

        if goal.complexity == GoalComplexity.SIMPLE:
            graph = self._plan_simple(goal)
        elif goal.complexity == GoalComplexity.MODERATE:
            graph = self._plan_moderate(goal)
        else:
            graph = self._plan_complex(goal)

        errors = graph.validate()
        if errors:
            raise PlanningError(f"Invalid plan: {'; '.join(errors)}")

        logger.info(
            "Planned goal [goal_id=%s, tasks=%d, complexity=%s]",
            goal.id,
            graph.task_count,
            goal.complexity.value,
        )

        return graph

    def replan(
        self,
        goal: Goal,
        existing_graph: TaskGraph,
        failed_task_id: str,
    ) -> TaskGraph:
        """Create a new plan after a task failure.

        Preserves completed tasks and creates replacement tasks where possible.
        """
        failed_task = existing_graph.get_task(failed_task_id)
        if not failed_task:
            raise PlanningError(f"Failed task '{failed_task_id}' not found in graph")

        new_graph = TaskGraph(
            goal_id=goal.id,
            description=f"Replan after failure of task '{failed_task_id}'",
        )

        for task in existing_graph.tasks:
            if task.id == failed_task_id:
                continue
            new_task = Task.from_dict(task.to_dict())
            if failed_task_id in new_task.dependencies:
                new_task.dependencies.remove(failed_task_id)
            new_graph.add_task(new_task)

        replacement = Task(
            description=f"Retry/replacement for: {failed_task.description}",
            objective=failed_task.objective,
            dependencies=[],
            assigned_agent=failed_task.assigned_agent,
            required_capabilities=failed_task.required_capabilities,
            required_tools=failed_task.required_tools,
            input_data=failed_task.input_data,
            verification_criteria=failed_task.verification_criteria,
            priority=failed_task.priority,
            max_retries=failed_task.max_retries,
            metadata={"replan_of": failed_task_id, "replan_reason": failed_task.error},
        )

        affected_dependents = [
            t for t in existing_graph.tasks
            if failed_task_id in t.dependencies and t.id != failed_task_id
        ]
        for dep_task in affected_dependents:
            replacement.dependents.append(dep_task.id)

        new_graph.add_task(replacement)

        errors = new_graph.validate()
        if errors:
            raise PlanningError(f"Invalid replan: {'; '.join(errors)}")

        logger.info(
            "Replanned goal [goal_id=%s, original_task=%s, new_tasks=%d]",
            goal.id,
            failed_task_id,
            new_graph.task_count,
        )

        return new_graph

    def _plan_simple(self, goal: Goal) -> TaskGraph:
        """Plan a simple goal as a single task."""
        graph = TaskGraph(goal_id=goal.id, description=goal.description)

        capabilities = goal.required_capabilities or self._infer_capabilities(goal)
        tools = goal.required_tools or self._infer_tools(goal)

        task = Task(
            description=goal.description,
            objective=goal.original_request,
            required_capabilities=capabilities,
            required_tools=tools,
            verification_criteria=[c.description for c in goal.success_criteria],
            priority=TaskPriority(goal.priority.value),
            metadata={"goal_id": goal.id, "planning": "simple"},
        )

        graph.add_task(task)
        return graph

    def _plan_moderate(self, goal: Goal) -> TaskGraph:
        """Plan a moderate goal with minimal decomposition."""
        graph = TaskGraph(goal_id=goal.id, description=goal.description)

        capabilities = goal.required_capabilities or self._infer_capabilities(goal)
        tools = goal.required_tools or self._infer_tools(goal)

        needs_analysis = any(c in capabilities for c in ["research", "analysis"])
        needs_execution = any(t in tools for t in [
            "create_file", "read_file", "search_files", "open_url", "open_app",
        ])
        needs_verification = len(goal.success_criteria) > 1

        tasks: List[Task] = []

        if needs_analysis:
            analysis_task = Task(
                description=f"Analyze: {goal.description}",
                objective=f"Analyze requirements for: {goal.original_request}",
                required_capabilities=["analysis", "research"],
                required_tools=[t for t in tools if t in ["read_file", "search_files", "open_url"]],
                metadata={"phase": "analysis", "goal_id": goal.id},
            )
            tasks.append(analysis_task)

        if needs_execution:
            exec_task = Task(
                description=f"Execute: {goal.description}",
                objective=goal.original_request,
                required_capabilities=[c for c in capabilities if c not in ["analysis", "research"]],
                required_tools=[t for t in tools if t not in ["read_file", "search_files", "open_url"]],
                metadata={"phase": "execution", "goal_id": goal.id},
            )
            if needs_analysis:
                exec_task.dependencies.append(tasks[0].id)
            tasks.append(exec_task)

        if not tasks:
            task = Task(
                description=goal.description,
                objective=goal.original_request,
                required_capabilities=capabilities,
                required_tools=tools,
                verification_criteria=[c.description for c in goal.success_criteria],
                metadata={"goal_id": goal.id, "planning": "moderate_fallback"},
            )
            tasks.append(task)

        if needs_verification and len(tasks) > 0:
            verify_task = Task(
                description=f"Verify: {goal.description}",
                objective=f"Verify results of: {goal.original_request}",
                required_capabilities=["analysis"],
                required_tools=[],
                verification_criteria=[c.description for c in goal.success_criteria],
                metadata={"phase": "verification", "goal_id": goal.id},
            )
            for t in tasks:
                verify_task.dependencies.append(t.id)
            tasks.append(verify_task)

        for t in tasks:
            graph.add_task(t)

        return graph

    def _plan_complex(self, goal: Goal) -> TaskGraph:
        """Plan a complex goal with full decomposition."""
        graph = TaskGraph(goal_id=goal.id, description=goal.description)

        capabilities = goal.required_capabilities or self._infer_capabilities(goal)
        tools = goal.required_tools or self._infer_tools(goal)

        tasks: List[Task] = []

        analysis_task = Task(
            description="Analyze requirements and gather context",
            objective=f"Analyze what is needed for: {goal.original_request}",
            required_capabilities=["analysis", "research"],
            required_tools=[t for t in tools if t in ["read_file", "search_files", "open_url"]],
            metadata={"phase": "analysis", "goal_id": goal.id},
        )
        tasks.append(analysis_task)

        if "research" in capabilities:
            research_task = Task(
                description="Research and gather information",
                objective=f"Research relevant information for: {goal.original_request}",
                required_capabilities=["research"],
                required_tools=["read_file", "search_files", "open_url"],
                dependencies=[analysis_task.id],
                metadata={"phase": "research", "goal_id": goal.id},
            )
            tasks.append(research_task)

        execution_tasks: List[Task] = []
        action_capabilities = [c for c in capabilities if c not in ["analysis", "research"]]
        action_tools = [t for t in tools if t not in ["read_file", "search_files", "open_url"]]

        if action_capabilities or action_tools:
            exec_task = Task(
                description="Execute core actions",
                objective=goal.original_request,
                required_capabilities=action_capabilities or capabilities,
                required_tools=action_tools or tools,
                dependencies=[tasks[-1].id],
                metadata={"phase": "execution", "goal_id": goal.id},
            )
            tasks.append(exec_task)
            execution_tasks.append(exec_task)

        if goal.success_criteria:
            verify_task = Task(
                description="Verify results against success criteria",
                objective="Verify all success criteria are met",
                required_capabilities=["analysis"],
                required_tools=[],
                verification_criteria=[c.description for c in goal.success_criteria],
                dependencies=[t.id for t in tasks[1:]],
                metadata={"phase": "verification", "goal_id": goal.id},
            )
            tasks.append(verify_task)

        summary_task = Task(
            description="Generate final summary",
            objective="Summarize results and produce final output",
            required_capabilities=["writing"],
            required_tools=[],
            dependencies=[tasks[-1].id],
            metadata={"phase": "summary", "goal_id": goal.id},
        )
        tasks.append(summary_task)

        for t in tasks[:self._max_tasks]:
            graph.add_task(t)

        if len(tasks) > self._max_tasks:
            logger.warning(
                "Plan truncated: %d tasks reduced to %d",
                len(tasks),
                self._max_tasks,
            )

        return graph

    def _infer_capabilities(self, goal: Goal) -> List[str]:
        """Infer required capabilities from goal description."""
        desc = goal.description.lower()
        caps = []

        if any(w in desc for w in ["research", "search", "find", "investigate"]):
            caps.append("research")
        if any(w in desc for w in ["code", "implement", "develop", "script"]):
            caps.append("coding")
        if any(w in desc for w in ["write", "draft", "document", "report", "summary"]):
            caps.append("writing")
        if any(w in desc for w in ["file", "directory", "create", "read"]):
            caps.append("filesystem")
        if any(w in desc for w in ["analyze", "compare", "evaluate"]):
            caps.append("analysis")
        if any(w in desc for w in ["browse", "website", "url"]):
            caps.append("browser")

        if not caps:
            caps.append("general")

        return caps

    def _infer_tools(self, goal: Goal) -> List[str]:
        """Infer required tools from goal description."""
        desc = goal.description.lower()
        tools = []

        if any(w in desc for w in ["create file", "write file", "save file"]):
            tools.append("create_file")
        if any(w in desc for w in ["read file", "open file", "view file"]):
            tools.append("read_file")
        if any(w in desc for w in ["search", "find", "list files"]):
            tools.append("search_files")
        if any(w in desc for w in ["url", "website", "browse"]):
            tools.append("open_url")
        if any(w in desc for w in ["screenshot", "capture"]):
            tools.append("take_screenshot")
        if any(w in desc for w in ["system", "cpu", "memory", "disk"]):
            tools.append("get_system_info")

        return tools


__all__ = ["GoalPlanner", "PlanningError"]
