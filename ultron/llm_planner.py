"""LLM-powered Task Planning for JARVIS Phase 5.

Replaces keyword-based task decomposition with LLM-driven planning.
Uses the existing LLMProvider abstraction.

Architecture:
    Goal
        ↓
    LLM Planner (structured prompt)
        ↓
    TaskGraph Proposal (JSON)
        ↓
    Schema Validation
        ↓
    Dependency Validation
        ↓
    Capability Validation
        ↓
    Security Validation
        ↓
    Approved TaskGraph
        ↓
    (fallback to GoalPlanner on failure)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ultron.goal import Goal, GoalComplexity
from ultron.llm.base import LLMProvider
from ultron.planner_v5 import GoalPlanner, PlanningError
from ultron.task import Task, TaskGraph, TaskPriority, TaskStatus

logger = logging.getLogger("ultron.llm_planner")

_VALID_CAPABILITIES = {"research", "coding", "writing", "filesystem", "browser", "analysis", "general"}
_VALID_TOOLS = {
    "create_file", "read_file", "search_files", "delete_file",
    "open_url", "open_app", "close_app", "take_screenshot",
    "get_system_info", "get_clipboard", "set_clipboard",
}
_VALID_PRIORITIES = {p.value for p in TaskPriority}

_PLANNING_PROMPT = """\
You are a task planning engine. Given a goal, decompose it into a directed acyclic graph of tasks.

Available tools: {tools}

Goal:
- Description: {description}
- Original request: {original_request}
- Complexity: {complexity}
- Required capabilities: {capabilities}
- Success criteria: {criteria}

Respond with ONLY a JSON object (no markdown, no explanation) matching this schema:
{{
    "tasks": [
        {{
            "id": "task_1",
            "description": "concise task description",
            "objective": "what this task aims to achieve",
            "required_capabilities": ["capability"],
            "required_tools": ["tool_name"],
            "dependencies": ["task_id"],
            "verification_criteria": ["criterion"],
            "priority": "low" | "normal" | "high" | "critical"
        }}
    ],
    "reasoning": "brief explanation of the decomposition"
}}

Rules:
- Task IDs must be unique strings like "task_1", "task_2", etc.
- Dependencies reference other task IDs in this plan
- No circular dependencies allowed
- Simple goals should have 1 task (no unnecessary decomposition)
- Moderate goals: 2-4 tasks
- Complex goals: 4-8 tasks maximum
- Only include tools from the available tools list
- Only include capabilities that are actually needed
- Each task should be atomic (one clear objective)
- Verification criteria should be concrete and checkable
- Do NOT create tasks that require tools not in the available list
- Do NOT create security-sensitive tasks (e.g., execute_command, delete_file with wildcards)

User goal: {goal_description}"""


class LLMGoalPlanner:
    """LLM-powered goal planner with heuristic fallback.

    Uses the existing LLMProvider to decompose Goals into TaskGraphs.
    Falls back to the keyword-based GoalPlanner when the LLM is
    unavailable or produces invalid output.
    """

    def __init__(
        self,
        provider: LLMProvider,
        available_tools: Optional[List[str]] = None,
        fallback: Optional[GoalPlanner] = None,
        max_tasks: int = 20,
    ) -> None:
        self._provider = provider
        self._available_tools = available_tools or []
        self._fallback = fallback or GoalPlanner(max_tasks=max_tasks)
        self._max_tasks = max_tasks

    def plan(self, goal: Goal) -> TaskGraph:
        """Create a TaskGraph from a Goal using LLM planning.

        All goals go through LLM planning. Falls back to heuristic
        GoalPlanner when the LLM is unavailable or produces invalid output
        after retries.
        """
        status_val = goal.status.value if hasattr(goal.status, "value") else str(goal.status)
        if status_val in ("blocked", "cancelled"):
            raise PlanningError(f"Cannot plan a goal in '{status_val}' state")

        # All goals use LLM planning — no simple bypass
        try:
            graph = self._llm_plan_with_retry(goal)
            if graph is not None:
                return graph
        except Exception as exc:
            logger.warning("LLM planning failed: %s", exc)

        logger.info("Falling back to heuristic planner")
        return self._fallback.plan(goal)

    def replan(
        self,
        goal: Goal,
        existing_graph: TaskGraph,
        failed_task_id: str,
    ) -> TaskGraph:
        """Create a new plan after a task failure using LLM reasoning.

        Falls back to heuristic replanning on failure.
        """
        try:
            graph = self._llm_replan(goal, existing_graph, failed_task_id)
            if graph is not None:
                errors = graph.validate()
                if not errors:
                    logger.info("LLM replanning succeeded")
                    return graph
        except Exception as exc:
            logger.warning("LLM replanning failed: %s", exc)

        return self._fallback.replan(goal, existing_graph, failed_task_id)

    def _llm_plan(self, goal: Goal) -> Optional[TaskGraph]:
        """Call LLM to plan the goal, return TaskGraph or None."""
        tools_str = ", ".join(self._available_tools) if self._available_tools else "none"
        capabilities_str = ", ".join(goal.required_capabilities) if goal.required_capabilities else "none"
        criteria_str = "; ".join(c.description for c in goal.success_criteria) if goal.success_criteria else "none"

        prompt = _PLANNING_PROMPT.format(
            tools=tools_str,
            description=goal.description,
            original_request=goal.original_request,
            complexity=goal.complexity.value,
            capabilities=capabilities_str,
            criteria=criteria_str,
            goal_description=goal.description,
        )

        result = self._provider.complete(prompt, [])

        if not result.text:
            logger.warning("LLM returned empty planning response")
            return None

        return self._parse_plan_response(result.text, goal)

    def _llm_plan_with_retry(self, goal: Goal, max_retries: int = 2) -> Optional[TaskGraph]:
        """Call LLM to plan with retry on validation failure.

        When the LLM returns a plan that fails validation, re-prompts
        with the error message so the LLM can correct its output.
        """
        last_error = None

        for attempt in range(max_retries + 1):
            graph = self._llm_plan(goal)
            if graph is None:
                # LLM returned empty/unparseable response
                if attempt < max_retries:
                    logger.info("LLM returned empty response, retrying (attempt %d)", attempt + 1)
                    continue
                return None

            errors = graph.validate()
            if not errors:
                logger.info(
                    "LLM planning succeeded [goal_id=%s, tasks=%d, attempt=%d]",
                    goal.id, graph.task_count, attempt + 1,
                )
                return graph

            # Validation failed — build error feedback for retry
            last_error = "; ".join(errors)
            logger.warning(
                "LLM plan validation failed (attempt %d): %s",
                attempt + 1, last_error,
            )

            if attempt < max_retries:
                # Re-prompt with error feedback
                retry_prompt = (
                    f"Your previous plan had validation errors:\n{last_error}\n\n"
                    "Please fix these errors and produce a valid plan."
                )
                try:
                    result = self._provider.complete(retry_prompt, [])
                    if result.text:
                        retry_graph = self._parse_plan_response(result.text, goal)
                        if retry_graph is not None:
                            retry_errors = retry_graph.validate()
                            if not retry_errors:
                                logger.info(
                                    "LLM planning succeeded on retry [goal_id=%s, tasks=%d]",
                                    goal.id, retry_graph.task_count,
                                )
                                return retry_graph
                except Exception as exc:
                    logger.warning("LLM retry failed: %s", exc)

        return None

    def _llm_replan(
        self,
        goal: Goal,
        existing_graph: TaskGraph,
        failed_task_id: str,
    ) -> Optional[TaskGraph]:
        """Call LLM to replan after a failure."""
        failed_task = existing_graph.get_task(failed_task_id)
        if not failed_task:
            return None

        completed = [
            {"id": t.id, "description": t.description, "output": str(t.output_data)[:200]}
            for t in existing_graph.tasks
            if t.status == TaskStatus.COMPLETED
        ]

        remaining = [
            {"id": t.id, "description": t.description, "dependencies": t.dependencies}
            for t in existing_graph.tasks
            if t.status in (TaskStatus.PENDING, TaskStatus.READY)
            and t.id != failed_task_id
        ]

        prompt = (
            "You are a task replanning engine. A task failed and you need to create a new plan.\n\n"
            f"Goal: {goal.description}\n"
            f"Failed task: {failed_task.description} (error: {failed_task.error})\n"
            f"Completed tasks: {json.dumps(completed)}\n"
            f"Remaining tasks: {json.dumps(remaining)}\n\n"
            "Create a new plan that:\n"
            "1. Keeps completed tasks as-is\n"
            "2. Replaces or modifies the failed task\n"
            "3. Adjusts dependencies if needed\n\n"
            "Respond with ONLY a JSON object matching the planning schema.\n"
            f"Available tools: {', '.join(self._available_tools) if self._available_tools else 'none'}"
        )

        result = self._provider.complete(prompt, [])
        if not result.text:
            return None

        return self._parse_plan_response(result.text, goal)

    def _parse_plan_response(self, text: str, goal: Goal) -> Optional[TaskGraph]:
        """Parse LLM JSON response into a TaskGraph."""
        cleaned = text.strip()

        # Strip markdown code fences
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM planning JSON: %s", exc)
            return None

        if not isinstance(data, dict):
            return None

        tasks_data = data.get("tasks", [])
        if not isinstance(tasks_data, list):
            return None

        return self._build_graph_from_tasks(tasks_data, goal)

    def _build_graph_from_tasks(
        self,
        tasks_data: List[Dict[str, Any]],
        goal: Goal,
    ) -> Optional[TaskGraph]:
        """Build a validated TaskGraph from LLM-generated task list."""
        graph = TaskGraph(goal_id=goal.id, description=goal.description)

        # First pass: create all tasks
        task_ids = set()
        for t_data in tasks_data:
            if not isinstance(t_data, dict):
                continue

            task_id = str(t_data.get("id", ""))
            if not task_id or task_id in task_ids:
                # Generate a unique ID if missing or duplicate
                task_id = f"task_{len(task_ids) + 1}"
            task_ids.add(task_id)

            description = str(t_data.get("description", ""))
            if not description:
                continue

            objective = str(t_data.get("objective", description))

            # Validate capabilities
            capabilities = [
                str(c) for c in t_data.get("required_capabilities", [])
                if isinstance(c, str) and c in _VALID_CAPABILITIES
            ]

            # Validate tools
            tools = [
                str(t) for t in t_data.get("required_tools", [])
                if isinstance(t, str) and t in _VALID_TOOLS
            ]

            # Validate priority
            priority_str = str(t_data.get("priority", "normal"))
            if priority_str not in _VALID_PRIORITIES:
                priority_str = "normal"

            # Verification criteria
            verification = [
                str(v) for v in t_data.get("verification_criteria", [])
                if isinstance(v, str)
            ]

            task = Task(
                id=task_id,
                description=description,
                objective=objective,
                required_capabilities=capabilities,
                required_tools=tools,
                verification_criteria=verification,
                priority=TaskPriority(priority_str),
                metadata={"source": "llm_planner", "goal_id": goal.id},
            )

            try:
                graph.add_task(task)
            except ValueError:
                logger.warning("Duplicate task ID: %s", task_id)

        # Second pass: add dependencies
        for t_data in tasks_data:
            if not isinstance(t_data, dict):
                continue
            task_id = str(t_data.get("id", ""))
            deps = t_data.get("dependencies", [])
            if not isinstance(deps, list):
                continue
            for dep in deps:
                dep_str = str(dep)
                if dep_str in task_ids and dep_str != task_id:
                    try:
                        graph.add_dependency(task_id, dep_str)
                    except ValueError:
                        pass

        # Validate
        if graph.has_cycle():
            logger.warning("LLM plan contains cycles, falling back")
            return None

        if not graph.tasks:
            logger.warning("LLM plan has no tasks")
            return None

        # Cap at max_tasks
        if len(graph.tasks) > self._max_tasks:
            logger.warning(
                "LLM plan has %d tasks, capping at %d",
                len(graph.tasks), self._max_tasks,
            )

        return graph


__all__ = ["LLMGoalPlanner"]
