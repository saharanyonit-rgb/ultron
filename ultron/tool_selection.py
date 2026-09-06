"""Intelligent Tool Selection for JARVIS Phase 5.

Provides structured tool selection that considers:
- Task requirements and capability matching
- Risk classification
- Tool failure history
- LLM-assisted selection for ambiguous cases
- Validation against ToolRegistry

Architecture:
    Task Requirements
        ↓
    Tool Selector
        ↓
    Capability Match → Risk Check → History Check → Validation
        ↓
    Ranked Tool List
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.llm.base import LLMProvider, ProviderResult
from ultron.risk import RiskClassifier, RiskLevel
from ultron.tools import Tool, ToolRegistry

logger = logging.getLogger("ultron.tool_selection")


@dataclass
class ToolSelection:
    """A ranked tool selection with reasoning."""
    tool_name: str
    score: float
    reasoning: str = ""
    risk_level: str = ""
    available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "score": self.score,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "available": self.available,
        }


@dataclass
class ToolSelectionResult:
    """Result of intelligent tool selection."""
    selected_tools: List[ToolSelection] = field(default_factory=list)
    primary_tool: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_tools": [t.to_dict() for t in self.selected_tools],
            "primary_tool": self.primary_tool,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


class ToolSelector:
    """Intelligent tool selector that considers multiple factors.

    Factors:
    1. Capability match: does the tool's capability match the task?
    2. Risk level: lower risk preferred when alternatives exist
    3. Failure history: tools that recently failed are deprioritized
    4. LLM reasoning: for ambiguous selections, ask the LLM
    5. Registry validation: only select tools that exist
    """

    def __init__(
        self,
        registry: ToolRegistry,
        risk_classifier: Optional[RiskClassifier] = None,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        self._registry = registry
        self._risk_classifier = risk_classifier or RiskClassifier()
        self._provider = provider
        self._failure_history: Dict[str, int] = {}  # tool_name -> failure count
        self._success_history: Dict[str, int] = {}  # tool_name -> success count

    def record_failure(self, tool_name: str) -> None:
        """Record a tool failure for future selection."""
        self._failure_history[tool_name] = self._failure_history.get(tool_name, 0) + 1

    def record_success(self, tool_name: str) -> None:
        """Record a tool success for future selection."""
        self._success_history[tool_name] = self._success_history.get(tool_name, 0) + 1

    def clear_history(self) -> None:
        """Clear failure and success history."""
        self._failure_history.clear()
        self._success_history.clear()

    def select_tools(
        self,
        task_description: str,
        required_tools: Optional[List[str]] = None,
        required_capabilities: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> ToolSelectionResult:
        """Select the best tools for a task.

        Args:
            task_description: What the task aims to do
            required_tools: Tools the task plan specifies
            required_capabilities: Capabilities needed
            max_results: Maximum number of tools to return

        Returns:
            ToolSelectionResult with ranked tool selections
        """
        # Get all available tools
        all_tools = self._registry.all()
        tool_names = {t.name: t for t in all_tools}

        # Filter to required tools if specified
        if required_tools:
            candidate_names = [t for t in required_tools if t in tool_names]
        else:
            candidate_names = list(tool_names.keys())

        if not candidate_names:
            return ToolSelectionResult(
                reasoning="No matching tools found in registry",
                confidence=1.0,
            )

        # Score each candidate
        selections = []
        for name in candidate_names:
            tool = tool_names[name]
            score = self._score_tool(tool, task_description, required_capabilities)
            risk = self._risk_classifier.classify(name)
            selections.append(ToolSelection(
                tool_name=name,
                score=score,
                risk_level=risk.value,
                available=True,
            ))

        # Sort by score descending
        selections.sort(key=lambda s: s.score, reverse=True)

        # Cap results
        selections = selections[:max_results]

        # Build result
        primary = selections[0].tool_name if selections else None
        avg_score = sum(s.score for s in selections) / len(selections) if selections else 0.0

        return ToolSelectionResult(
            selected_tools=selections,
            primary_tool=primary,
            reasoning=f"Selected {len(selections)} tools from {len(candidate_names)} candidates",
            confidence=min(avg_score, 1.0),
        )

    def select_with_llm(
        self,
        task_description: str,
        available_tools: Optional[List[str]] = None,
    ) -> ToolSelectionResult:
        """Use LLM to select the best tool for an ambiguous task.

        Falls back to rule-based selection if LLM is unavailable.
        """
        if not self._provider:
            return self.select_tools(task_description, required_tools=available_tools)

        tools_str = ", ".join(available_tools) if available_tools else "all registered tools"

        prompt = (
            f"Select the best tool for this task:\n"
            f"Task: {task_description}\n"
            f"Available tools: {tools_str}\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"tool_name": "...", "reasoning": "...", "confidence": 0.0-1.0}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_llm_selection(result.text, available_tools)
        except Exception as exc:
            logger.warning("LLM tool selection failed: %s", exc)

        return self.select_tools(task_description, required_tools=available_tools)

    def _score_tool(
        self,
        tool: Tool,
        task_description: str,
        required_capabilities: Optional[List[str]] = None,
    ) -> float:
        """Score a tool's suitability for a task."""
        score = 0.5  # base score

        # Capability match bonus
        tool_desc = tool.description.lower()
        task_lower = task_description.lower()

        # Simple keyword matching
        task_words = set(task_lower.split())
        desc_words = set(tool_desc.split())
        overlap = len(task_words & desc_words)
        if overlap > 0:
            score += min(overlap * 0.05, 0.2)

        # Risk penalty: higher risk = lower score
        risk = self._risk_classifier.classify(tool.name)
        risk_penalties = {
            RiskLevel.READ: 0.0,
            RiskLevel.LOW: -0.05,
            RiskLevel.MEDIUM: -0.1,
            RiskLevel.HIGH: -0.2,
            RiskLevel.CRITICAL: -0.3,
        }
        score += risk_penalties.get(risk, 0)

        # Failure history penalty
        failures = self._failure_history.get(tool.name, 0)
        if failures > 0:
            score -= min(failures * 0.1, 0.3)

        # Success history bonus
        successes = self._success_history.get(tool.name, 0)
        if successes > 0:
            score += min(successes * 0.05, 0.15)

        return max(0.0, min(1.0, score))

    def _parse_llm_selection(
        self,
        text: str,
        available_tools: Optional[List[str]] = None,
    ) -> ToolSelectionResult:
        """Parse LLM tool selection response."""
        cleaned = text.strip()
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
                tool_name = data.get("tool_name", "")
                reasoning = data.get("reasoning", "")
                confidence = float(data.get("confidence", 0.5))

                # Validate tool exists
                if available_tools and tool_name not in available_tools:
                    tool_name = None
                elif tool_name and not self._registry.exists(tool_name):
                    tool_name = None

                if tool_name:
                    risk = self._risk_classifier.classify(tool_name)
                    return ToolSelectionResult(
                        selected_tools=[ToolSelection(
                            tool_name=tool_name,
                            score=confidence,
                            reasoning=reasoning,
                            risk_level=risk.value,
                        )],
                        primary_tool=tool_name,
                        reasoning=reasoning,
                        confidence=confidence,
                    )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Fallback to rule-based
        return self.select_tools("", required_tools=available_tools)


__all__ = [
    "ToolSelection",
    "ToolSelectionResult",
    "ToolSelector",
]
