"""Data Types for Phase 5 Semantic Verification.

Defines result schema objects: SemanticCheckResult, SemanticVerificationResult, EvidenceItem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SemanticCheckResult:
    """Result of a single semantic verification check."""
    criterion: str = ""
    passed: bool = False
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion,
            "passed": self.passed,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


@dataclass
class SemanticVerificationResult:
    """Complete semantic verification result."""
    overall_passed: bool = False
    confidence: float = 0.0
    checks: List[SemanticCheckResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_passed": self.overall_passed,
            "confidence": self.confidence,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
        }


@dataclass
class EvidenceItem:
    """A piece of evidence extracted from task output."""
    source: str = ""
    content: str = ""
    relevance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "content": self.content,
            "relevance": self.relevance,
        }


__all__ = [
    "SemanticCheckResult",
    "SemanticVerificationResult",
    "EvidenceItem",
]
