"""Verification Brain for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

The Verification Brain is responsible for:
- Evaluating expected vs actual results
- Checking evidence
- Inspecting test output
- Inspecting tool output
- Checking execution state
- Returning structured verification results

The Verification Brain does NOT blindly trust the agent that performed the task.
It is an independent verification layer.

Verification statuses:
- passed: The task achieved its expected outcome
- failed: The task did not achieve its expected outcome
- inconclusive: Cannot determine success or failure

Recommendations:
- complete: The goal is complete, proceed to next
- retry: Retry the task with same or different approach
- replan: Generate a new plan
- switch_agent: Use a different agent
- ask_user: Request user clarification
- abort: Stop execution
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.brains.verification")

VERIFICATION_SYSTEM_PROMPT = """You are the Verification Brain for JARVIS. Your role is to independently verify whether tasks achieved their expected outcomes.

You do NOT trust the agent that performed the task. You must verify objectively.

Given a task description, expected outcome, and actual results, you must:
1. Compare expected vs actual
2. Check evidence (tool outputs, test results)
3. Identify failures or discrepancies
4. Provide a clear verification status and recommendation

Output format:
{
    "status": "passed|failed|inconclusive",
    "confidence": 0.0-1.0,
    "evidence": ["list of evidence items"],
    "failures": ["list of failure descriptions"],
    "recommendation": "complete|retry|replan|switch_agent|ask_user|abort",
    "reasoning": "Why this verification result"
}

Rules:
- Be objective and skeptical
- Check actual evidence, not claims
- If evidence is missing, status should be inconclusive
- Recommend retry only if the failure was likely transient
- Recommend abort only for critical failures"""


class VerificationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class VerificationRecommendation(str, Enum):
    COMPLETE = "complete"
    RETRY = "retry"
    REPLAN = "replan"
    SWITCH_AGENT = "switch_agent"
    ASK_USER = "ask_user"
    ABORT = "abort"


@dataclass
class VerificationResult:
    """Result of verification."""

    status: VerificationStatus
    confidence: float
    evidence: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    recommendation: VerificationRecommendation = VerificationRecommendation.COMPLETE
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "failures": self.failures,
            "recommendation": self.recommendation.value if isinstance(self.recommendation, Enum) else self.recommendation,
            "reasoning": self.reasoning,
        }


class VerificationBrain(BaseAgent):
    """Specialized agent for independent verification of task results."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 5,
    ) -> None:
        spec = AgentSpec(
            name="verification",
            description="Independent verification of task results",
            capabilities=[AgentCapability.GENERAL],
            allowed_tools=[],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)

    def verify(
        self,
        task_description: str,
        expected_outcome: str,
        actual_result: Any,
        evidence: Optional[List[str]] = None,
    ) -> VerificationResult:
        """Verify whether a task achieved its expected outcome.

        Args:
            task_description: What the task was supposed to do
            expected_outcome: What the expected result was
            actual_result: The actual result from task execution
            evidence: Optional list of evidence (tool outputs, etc.)

        Returns:
            VerificationResult with status and recommendation
        """
        prompt = self._build_verification_prompt(
            task_description,
            expected_outcome,
            actual_result,
            evidence,
        )

        result = self._provider.complete(prompt, [])

        if result.text:
            return self._parse_verification_result(result.text)

        return VerificationResult(
            status=VerificationStatus.INCONCLUSIVE,
            confidence=0.0,
            failures=["Failed to get verification result from model"],
            recommendation=VerificationRecommendation.ASK_USER,
            reasoning="Verification model did not return a result",
        )

    def _build_verification_prompt(
        self,
        task_description: str,
        expected_outcome: str,
        actual_result: Any,
        evidence: Optional[List[str]],
    ) -> str:
        parts = [
            VERIFICATION_SYSTEM_PROMPT,
            f"\nTask Description:\n{task_description}",
            f"\nExpected Outcome:\n{expected_outcome}",
            f"\nActual Result:\n{actual_result}",
        ]

        if evidence:
            parts.append(f"\nEvidence:\n" + "\n".join(f"- {e}" for e in evidence))

        parts.append('\nOutput format: {"status": "...", "confidence": 0.0-1.0, "evidence": [], "failures": [], "recommendation": "...", "reasoning": "..."}')

        return "\n".join(parts)

    def _parse_verification_result(self, text: str) -> VerificationResult:
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

            status_str = data.get("status", "inconclusive")
            try:
                status = VerificationStatus(status_str)
            except ValueError:
                status = VerificationStatus.INCONCLUSIVE

            recommendation_str = data.get("recommendation", "complete")
            try:
                recommendation = VerificationRecommendation(recommendation_str)
            except ValueError:
                recommendation = VerificationRecommendation.COMPLETE

            return VerificationResult(
                status=status,
                confidence=float(data.get("confidence", 0.5)),
                evidence=data.get("evidence", []),
                failures=data.get("failures", []),
                recommendation=recommendation,
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            logger.warning("Failed to parse verification JSON: %s", cleaned[:200])
            return VerificationResult(
                status=VerificationStatus.INCONCLUSIVE,
                confidence=0.0,
                failures=[f"Failed to parse verification result: {cleaned[:100]}"],
                recommendation=VerificationRecommendation.ASK_USER,
                reasoning="Failed to parse model output as JSON",
            )

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute verification - requires structured context.

        For simple use, prefer verify() method with structured parameters.
        """
        if context:
            return json.dumps(self.verify(
                task_description=context.get("task_description", user_text),
                expected_outcome=context.get("expected_outcome", ""),
                actual_result=context.get("actual_result", ""),
                evidence=context.get("evidence", []),
            ).to_dict(), ensure_ascii=False, default=str)

        return json.dumps(VerificationResult(
            status=VerificationStatus.INCONCLUSIVE,
            confidence=0.0,
            failures=["Verification requires structured context"],
            recommendation=VerificationRecommendation.ASK_USER,
            reasoning="No context provided for verification",
        ).to_dict(), ensure_ascii=False, default=str)


__all__ = [
    "VerificationBrain",
    "VerificationStatus",
    "VerificationRecommendation",
    "VerificationResult",
]
