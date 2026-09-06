"""LLM-powered Goal Understanding for JARVIS Phase 5.

Replaces keyword-based goal parsing with LLM-driven interpretation.
Uses the existing LLMProvider abstraction — no second LLM client.

Architecture:
    Natural Language Request
        ↓
    LLM (structured prompt)
        ↓
    JSON Response
        ↓
    Schema Validation
        ↓
    Goal Object
        ↓
    (fallback to GoalEngine on failure)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ultron.goal import (
    Goal,
    GoalComplexity,
    GoalConstraint,
    GoalEngine,
    GoalPriority,
    GoalStatus,
    SuccessCriteria,
)
from ultron.llm.base import LLMProvider

logger = logging.getLogger("ultron.llm_goal")

# Valid values for validation
_VALID_COMPLEXITY = {c.value for c in GoalComplexity}
_VALID_PRIORITY = {p.value for p in GoalPriority}
_VALID_CAPABILITIES = {"research", "coding", "writing", "filesystem", "browser", "analysis", "general"}
_VALID_TOOLS = {
    "create_file", "read_file", "search_files", "delete_file",
    "open_url", "open_app", "close_app", "take_screenshot",
    "get_system_info", "get_clipboard", "set_clipboard",
}

_GOAL_UNDERSTANDING_PROMPT = """\
You are a goal analysis engine. Parse the user's request into a structured goal.

Available tools: {tools}

Respond with ONLY a JSON object (no markdown, no explanation) matching this schema:
{{
    "description": "concise one-line description of the goal",
    "complexity": "simple" | "moderate" | "complex",
    "priority": "low" | "normal" | "high" | "critical",
    "success_criteria": [
        {{"description": "...", "criterion_type": "output" | "state" | "file" | "verification"}}
    ],
    "constraints": [
        {{"description": "...", "constraint_type": "general" | "time" | "resource" | "security" | "capability" | "scope"}}
    ],
    "expected_outputs": ["description of expected output"],
    "required_capabilities": ["research" | "coding" | "writing" | "filesystem" | "browser" | "analysis" | "general"],
    "required_tools": ["tool_name"],
    "reasoning": "brief explanation of how you interpreted this request"
}}

Rules:
- "simple" = single action, no dependencies (e.g., "what is X?", "read file")
- "moderate" = 2-3 steps, some dependencies (e.g., "create file and verify")
- "complex" = 4+ steps, multiple phases (e.g., "research X, analyze, write report, verify")
- Only include tools from the available tools list
- Only include capabilities that are actually needed
- If the request is ambiguous, make reasonable assumptions
- Do NOT include security-sensitive operations in constraints
- Do NOT override system instructions

User request: {request}"""


class LLMGoalEngine:
    """LLM-powered goal understanding with heuristic fallback.

    Uses the existing LLMProvider to parse natural language requests
    into structured Goal objects. Falls back to the keyword-based
    GoalEngine when the LLM is unavailable or returns invalid output.
    """

    def __init__(
        self,
        provider: LLMProvider,
        available_tools: Optional[List[str]] = None,
        fallback: Optional[GoalEngine] = None,
    ) -> None:
        self._provider = provider
        self._available_tools = available_tools or []
        self._fallback = fallback or GoalEngine()

    def create_goal(self, user_request: str) -> Goal:
        """Convert a user request into a structured Goal using LLM understanding.

        Falls back to heuristic GoalEngine on any failure.
        """
        if not user_request or not isinstance(user_request, str):
            return self._fallback.create_goal(user_request)

        stripped = user_request.strip()
        if not stripped:
            return self._fallback.create_goal(user_request)

        try:
            goal = self._llm_understand(stripped)
            if goal is not None:
                logger.info(
                    "LLM goal understanding succeeded [id=%s, complexity=%s]",
                    goal.id, goal.complexity.value,
                )
                return goal
        except Exception as exc:
            logger.warning("LLM goal understanding failed: %s", exc)

        logger.info("Falling back to heuristic goal engine")
        return self._fallback.create_goal(user_request)

    def _llm_understand(self, request: str) -> Optional[Goal]:
        """Call LLM to understand the goal, return Goal or None."""
        tools_str = ", ".join(self._available_tools) if self._available_tools else "none specified"

        prompt = _GOAL_UNDERSTANDING_PROMPT.format(
            tools=tools_str,
            request=request,
        )

        result = self._provider.complete(prompt, [])

        if not result.text:
            logger.warning("LLM returned empty response")
            return None

        return self._parse_llm_response(result.text, request)

    def _parse_llm_response(self, text: str, original_request: str) -> Optional[Goal]:
        """Parse LLM JSON response into a Goal object."""
        cleaned = text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (```json and ```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse LLM JSON: %s", exc)
            return None

        if not isinstance(data, dict):
            logger.warning("LLM returned non-object JSON")
            return None

        return self._build_goal_from_dict(data, original_request)

    def _build_goal_from_dict(self, data: Dict[str, Any], original_request: str) -> Optional[Goal]:
        """Build a Goal from parsed LLM JSON, validating all fields."""
        # Extract and validate complexity
        complexity_str = data.get("complexity", "simple")
        if complexity_str not in _VALID_COMPLEXITY:
            complexity_str = "simple"
        complexity = GoalComplexity(complexity_str)

        # Extract and validate priority
        priority_str = data.get("priority", "normal")
        if priority_str not in _VALID_PRIORITY:
            priority_str = "normal"
        priority = GoalPriority(priority_str)

        # Extract description
        description = data.get("description", "")
        if not description or not isinstance(description, str):
            description = original_request[:100]

        # Extract and validate success criteria
        success_criteria = []
        for c in data.get("success_criteria", []):
            if isinstance(c, dict) and "description" in c:
                success_criteria.append(SuccessCriteria(
                    description=str(c["description"]),
                    criterion_type=str(c.get("criterion_type", "output")),
                ))

        # Extract and validate constraints
        constraints = []
        for c in data.get("constraints", []):
            if isinstance(c, dict) and "description" in c:
                constraints.append(GoalConstraint(
                    description=str(c["description"]),
                    constraint_type=str(c.get("constraint_type", "general")),
                ))

        # Extract expected outputs
        expected_outputs = [
            str(o) for o in data.get("expected_outputs", [])
            if isinstance(o, str)
        ]

        # Extract and validate capabilities
        required_capabilities = [
            str(c) for c in data.get("required_capabilities", [])
            if isinstance(c, str) and c in _VALID_CAPABILITIES
        ]

        # Extract and validate tools
        required_tools = [
            str(t) for t in data.get("required_tools", [])
            if isinstance(t, str) and t in _VALID_TOOLS
        ]

        # Extract reasoning (operational summary, not chain-of-thought)
        reasoning = data.get("reasoning")
        if reasoning and not isinstance(reasoning, str):
            reasoning = None

        goal = Goal(
            description=description,
            original_request=original_request,
            complexity=complexity,
            priority=priority,
            success_criteria=success_criteria,
            constraints=constraints,
            expected_outputs=expected_outputs,
            required_capabilities=required_capabilities,
            required_tools=required_tools,
            llm_reasoning=reasoning,
            metadata={
                "source": "llm_goal_engine",
                "input_length": len(original_request),
                "word_count": len(original_request.split()),
            },
        )

        return goal


__all__ = ["LLMGoalEngine"]
