"""LLM-driven Recovery for JARVIS Phase 5.

Extends the existing RecoveryEngine with LLM-assisted failure analysis
and recovery strategy selection.

Architecture:
    Failure
        ↓
    Failure Classification (existing)
        ↓
    LLM Recovery Analysis
        ↓
    Structured Recovery Decision
        ↓
    Validation
        ↓
    Execute Recovery
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.llm.base import LLMProvider, ProviderResult
from ultron.recovery import (
    ErrorClass,
    RecoveryAction,
    RecoveryDecision,
    RecoveryEngine,
)
from ultron.execution_state import StepState

logger = logging.getLogger("ultron.intelligent_recovery")


@dataclass
class RecoveryAnalysis:
    """LLM's analysis of a failure."""
    error_summary: str = ""
    likely_cause: str = ""
    suggested_action: str = ""
    suggested_tool: Optional[str] = None
    suggested_arguments: Optional[Dict[str, Any]] = None
    confidence: float = 0.5
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_summary": self.error_summary,
            "likely_cause": self.likely_cause,
            "suggested_action": self.suggested_action,
            "suggested_tool": self.suggested_tool,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class IntelligentRecoveryEngine(RecoveryEngine):
    """RecoveryEngine extended with LLM-assisted analysis.

    When a task fails, the LLM analyzes:
    1. The error message and type
    2. The task description and objective
    3. Previous attempts
    4. Available tools

    Then suggests a recovery strategy with reasoning.
    Falls back to base heuristic on LLM failure.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        max_retries: int = 3,
        available_tools: Optional[List[str]] = None,
    ) -> None:
        super().__init__(max_retries=max_retries)
        self._provider = provider
        self._available_tools = available_tools or []

    def analyze_failure(
        self,
        step: StepState,
        error: Exception | str,
        task_description: str = "",
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> RecoveryAnalysis:
        """Use LLM to analyze a failure and suggest recovery."""
        if not self._provider:
            return self._heuristic_analysis(step, error)

        error_str = str(error)
        error_type = type(error).__name__ if isinstance(error, Exception) else "Unknown"

        prompt = (
            "Analyze this task failure and suggest a recovery strategy.\n\n"
            f"Task: {task_description}\n"
            f"Error type: {error_type}\n"
            f"Error message: {error_str}\n"
            f"Retry count: {step.retry_count}\n"
        )

        if previous_attempts:
            prompt += f"Previous attempts: {json.dumps(previous_attempts[:3], default=str)[:500]}\n"

        if self._available_tools:
            prompt += f"Available tools: {', '.join(self._available_tools)}\n"

        prompt += (
            "\nRespond with ONLY a JSON object:\n"
            '{"error_summary": "...", "likely_cause": "...", '
            '"suggested_action": "retry" | "change_tool" | "change_approach" | "replan" | "abort", '
            '"suggested_tool": "tool_name or null", '
            '"confidence": 0.0-1.0, "reasoning": "..."}'
        )

        try:
            result = self._provider.complete(prompt, [])
            if result.text:
                return self._parse_analysis(result.text)
        except Exception as exc:
            logger.warning("LLM recovery analysis failed: %s", exc)

        return self._heuristic_analysis(step, error)

    def decide_recovery_intelligent(
        self,
        step: StepState,
        error: Exception | str,
        task_description: str = "",
        previous_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> RecoveryDecision:
        """Make a recovery decision using LLM analysis."""
        # Get base decision
        base_decision = self.decide_recovery(step, error)

        # Get LLM analysis
        analysis = self.analyze_failure(step, error, task_description, previous_attempts)

        # Map analysis to recovery action
        action_map = {
            "retry": RecoveryAction.RETRY,
            "change_tool": RecoveryAction.RETRY,
            "change_approach": RecoveryAction.REPLAN,
            "replan": RecoveryAction.REPLAN,
            "abort": RecoveryAction.ABORT,
            "skip": RecoveryAction.SKIP,
        }

        llm_action = action_map.get(analysis.suggested_action, base_decision.action)

        # Use LLM action if confidence is high enough, otherwise use base
        # But always respect retry limits from the base engine
        if analysis.confidence >= 0.6 and base_decision.action != RecoveryAction.ABORT:
            action = llm_action
            reason = f"LLM analysis ({analysis.confidence:.0%}): {analysis.reasoning}"
        else:
            action = base_decision.action
            reason = f"Heuristic decision: {base_decision.reason}"

        decision = RecoveryDecision(
            action=action,
            reason=reason,
            error_class=base_decision.error_class,
            retry_count=step.retry_count,
            max_retries=base_decision.max_retries,
            previous_results=base_decision.previous_results,
        )

        return decision

    def _heuristic_analysis(
        self,
        step: StepState,
        error: Exception | str,
    ) -> RecoveryAnalysis:
        """Fallback heuristic analysis without LLM."""
        error_str = str(error)
        error_type = type(error).__name__ if isinstance(error, Exception) else "Unknown"

        return RecoveryAnalysis(
            error_summary=f"{error_type}: {error_str[:200]}",
            likely_cause="Unknown (heuristic analysis)",
            suggested_action="retry",
            confidence=0.3,
            reasoning="Heuristic fallback: defaulting to retry",
        )

    def _parse_analysis(self, text: str) -> RecoveryAnalysis:
        """Parse LLM analysis response."""
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
                return RecoveryAnalysis(
                    error_summary=str(data.get("error_summary", "")),
                    likely_cause=str(data.get("likely_cause", "")),
                    suggested_action=str(data.get("suggested_action", "retry")),
                    suggested_tool=data.get("suggested_tool"),
                    suggested_arguments=data.get("suggested_arguments"),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=str(data.get("reasoning", "")),
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        return RecoveryAnalysis(
            error_summary="Failed to parse LLM analysis",
            suggested_action="retry",
            confidence=0.2,
            reasoning="LLM returned unparseable response",
        )


__all__ = ["RecoveryAnalysis", "IntelligentRecoveryEngine"]
