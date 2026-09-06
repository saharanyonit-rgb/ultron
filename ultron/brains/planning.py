"""Planning Brain for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

The Planning Brain is responsible for:
- Understanding complex goals
- Decomposing goals into tasks
- Identifying dependencies
- Identifying required capabilities
- Producing machine-readable execution plans
- Detecting parallelizable tasks
- Detecting sequential dependencies

The Planning Brain does NOT directly execute tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.brains.planning")

PLANNING_SYSTEM_PROMPT = """You are the Planning Brain for JARVIS. Your role is to decompose complex goals into actionable execution plans.

You do NOT execute tools - you only plan.

Given a user request, you must produce a structured plan in JSON format:

{
    "goal": "The high-level goal",
    "tasks": [
        {
            "id": "task_1",
            "agent": "research|coding|computer|verification|fast",
            "description": "What this task does",
            "dependencies": [],
            "capabilities": ["research", "coding", etc],
            "parallel": true|false
        }
    ],
    "reasoning": "Why this plan was chosen"
}

Rules:
- Identify which tasks can run in parallel (no dependencies between them)
- Tasks with dependencies must run sequentially
- Assign the appropriate agent type to each task
- Keep tasks focused - one task per agent action
- If verification is needed, include a verification task at the end

Respond ONLY with the JSON plan, no additional text."""


@dataclass
class PlannedTask:
    """A single task in a plan."""

    id: str
    agent: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    parallel: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "description": self.description,
            "dependencies": self.dependencies,
            "capabilities": self.capabilities,
            "parallel": self.parallel,
        }


@dataclass
class ExecutionPlan:
    """A complete execution plan from the Planning Brain."""

    goal: str
    tasks: List[PlannedTask]
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "reasoning": self.reasoning,
        }

    def get_parallel_groups(self) -> List[List[PlannedTask]]:
        groups: List[List[PlannedTask]] = []
        completed: set = set()

        while completed != {t.id for t in self.tasks}:
            ready = [
                t for t in self.tasks
                if t.id not in completed and all(d in completed for d in t.dependencies)
            ]
            if not ready:
                break
            groups.append(ready)
            completed.update(t.id for t in ready)

        return groups


class PlanningBrain(BaseAgent):
    """Specialized agent for planning and goal decomposition."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 5,
    ) -> None:
        spec = AgentSpec(
            name="planning",
            description="Goal decomposition, task planning, workflow creation",
            capabilities=[AgentCapability.TASK, AgentCapability.GENERAL],
            allowed_tools=[],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)
        self._system_prompt = PLANNING_SYSTEM_PROMPT

    def plan(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> ExecutionPlan:
        """Create an execution plan for the given goal.

        Args:
            user_text: The user's request/goal
            context: Optional context with additional information

        Returns:
            ExecutionPlan with decomposed tasks
        """
        prompt = self._build_prompt(user_text, context)
        result = self._provider.complete(prompt, [])

        if result.text:
            return self._parse_plan(result.text, user_text)

        return ExecutionPlan(
            goal=user_text,
            tasks=[],
            reasoning="Failed to generate plan",
        )

    def _build_prompt(self, user_text: str, context: Optional[Dict[str, Any]]) -> str:
        parts = [self._system_prompt, f"\n\nUser Request:\n{user_text}"]

        if context:
            if "available_agents" in context:
                parts.append(f"\nAvailable Agents: {', '.join(context['available_agents'])}")
            if "available_tools" in context:
                parts.append(f"\nAvailable Tools: {', '.join(context['available_tools'])}")
            if "constraints" in context:
                parts.append(f"\nConstraints: {context['constraints']}")

        return "\n".join(parts)

    def _parse_plan(self, text: str, original_goal: str) -> ExecutionPlan:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            tasks = []
            for t in data.get("tasks", []):
                tasks.append(PlannedTask(
                    id=t.get("id", ""),
                    agent=t.get("agent", "fast"),
                    description=t.get("description", ""),
                    dependencies=t.get("dependencies", []),
                    capabilities=t.get("capabilities", []),
                    parallel=t.get("parallel", False),
                ))
            return ExecutionPlan(
                goal=data.get("goal", original_goal),
                tasks=tasks,
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            logger.warning("Failed to parse plan JSON: %s", cleaned[:200])
            return ExecutionPlan(
                goal=original_goal,
                tasks=[],
                reasoning=f"Failed to parse plan: {cleaned[:100]}",
            )

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute the planning brain - returns JSON plan as string.

        This method is required by BaseAgent but prefer using plan() for
        structured output.
        """
        plan = self.plan(user_text, context)
        return json.dumps(plan.to_dict(), ensure_ascii=False, default=str)


__all__ = ["PlanningBrain", "ExecutionPlan", "PlannedTask"]
