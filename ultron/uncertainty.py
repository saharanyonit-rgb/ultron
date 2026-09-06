"""Uncertainty Management for JARVIS Phase 5.

Provides explicit uncertainty handling so agents don't claim certainty
when evidence is insufficient.

Supports:
- Confidence scoring
- Ambiguity detection
- Insufficient-evidence detection
- Conflicting-result detection
- Escalation to user
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.uncertainty")


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class UncertaintyEvent:
    """Record of an uncertainty detection."""
    event_type: str = ""
    description: str = ""
    confidence_level: str = ConfidenceLevel.MEDIUM.value
    confidence_score: float = 0.5
    context: Dict[str, Any] = field(default_factory=dict)
    requires_action: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "description": self.description,
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "requires_action": self.requires_action,
        }


class UncertaintyHandler:
    """Handles uncertainty detection and escalation.

    Checks agent outputs for signs of uncertainty:
    - Hedging language ("might", "possibly", "not sure")
    - Low confidence scores
    - Contradictory statements
    - Insufficient evidence
    """

    HEDGING_PHRASES = {
        "might be", "could be", "possibly", "maybe", "perhaps",
        "not sure", "uncertain", "unclear", "hard to say",
        "it seems", "appears to", "likely", "probably",
        "i think", "i believe", "in my opinion",
        "not confident", "low confidence",
        "may", "might", "could",
    }

    CONTRADICTION_MARKERS = {
        "however", "but", "although", "on the other hand",
        "contradicts", "conflicts", "inconsistent",
    }

    def __init__(
        self,
        require_action_on_low_confidence: bool = False,
        min_confidence_threshold: float = 0.4,
    ) -> None:
        self._require_action = require_action_on_low_confidence
        self._min_threshold = min_confidence_threshold
        self._events: List[UncertaintyEvent] = []

    @property
    def events(self) -> List[UncertaintyEvent]:
        return list(self._events)

    def check_confidence(
        self,
        text: str,
        confidence_score: Optional[float] = None,
    ) -> UncertaintyEvent:
        """Check text for uncertainty signals."""
        text_lower = text.lower()

        # Check for hedging language
        hedging_found = [p for p in self.HEDGING_PHRASES if p in text_lower]

        # Check for contradiction markers
        contradictions = [m for m in self.CONTRADICTION_MARKERS if m in text_lower]

        # Determine confidence level
        if confidence_score is not None:
            score = confidence_score
        elif hedging_found:
            score = max(0.2, 0.7 - len(hedging_found) * 0.1)
        else:
            score = 0.7

        if score >= 0.7:
            level = ConfidenceLevel.HIGH
        elif score >= 0.4:
            level = ConfidenceLevel.MEDIUM
        elif score > 0.0:
            level = ConfidenceLevel.LOW
        else:
            level = ConfidenceLevel.UNKNOWN

        # Build event
        event = UncertaintyEvent(
            event_type="confidence_check",
            description=self._build_description(hedging_found, contradictions, score),
            confidence_level=level.value,
            confidence_score=score,
            context={
                "hedging_phrases": hedging_found,
                "contradiction_markers": contradictions,
            },
            requires_action=self._should_escalate(level, score),
        )

        self._events.append(event)
        return event

    def check_ambiguity(
        self,
        text: str,
        expected_topic: str = "",
    ) -> UncertaintyEvent:
        """Check if the response addresses the expected topic."""
        text_lower = text.lower()
        topic_lower = expected_topic.lower() if expected_topic else ""

        if topic_lower:
            topic_words = set(topic_lower.split())
            text_words = set(text_lower.split())
            overlap = len(topic_words & text_words)
            relevance = overlap / len(topic_words) if topic_words else 1.0
        else:
            relevance = 0.5

        score = min(1.0, relevance)
        level = (
            ConfidenceLevel.HIGH if score >= 0.7
            else ConfidenceLevel.MEDIUM if score >= 0.4
            else ConfidenceLevel.LOW
        )

        event = UncertaintyEvent(
            event_type="ambiguity_check",
            description=f"Topic relevance: {score:.0%}",
            confidence_level=level.value,
            confidence_score=score,
            requires_action=level == ConfidenceLevel.LOW,
        )

        self._events.append(event)
        return event

    def check_conflicting_results(
        self,
        results: List[Dict[str, Any]],
    ) -> UncertaintyEvent:
        """Check if multiple results conflict with each other."""
        if len(results) <= 1:
            return UncertaintyEvent(
                event_type="conflict_check",
                description="No conflicts (single result)",
                confidence_level=ConfidenceLevel.HIGH.value,
                confidence_score=1.0,
            )

        # Simple conflict detection: check if boolean results differ
        bool_results = []
        for r in results:
            if isinstance(r, dict):
                for v in r.values():
                    if isinstance(v, bool):
                        bool_results.append(v)

        if len(bool_results) >= 2:
            if len(set(bool_results)) > 1:
                event = UncertaintyEvent(
                    event_type="conflict_check",
                    description="Conflicting boolean results detected",
                    confidence_level=ConfidenceLevel.LOW.value,
                    confidence_score=0.2,
                    requires_action=True,
                    context={"conflicting_results": len(results)},
                )
                self._events.append(event)
                return event

        return UncertaintyEvent(
            event_type="conflict_check",
            description="No conflicts detected",
            confidence_level=ConfidenceLevel.HIGH.value,
            confidence_score=0.8,
        )

    def should_escalate(self, event: UncertaintyEvent) -> bool:
        """Determine if an uncertainty event requires user escalation."""
        return event.requires_action

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all uncertainty events."""
        if not self._events:
            return {"total_events": 0, "requires_action": 0}

        return {
            "total_events": len(self._events),
            "requires_action": sum(1 for e in self._events if e.requires_action),
            "average_confidence": sum(e.confidence_score for e in self._events) / len(self._events),
            "low_confidence_count": sum(
                1 for e in self._events
                if e.confidence_level in (ConfidenceLevel.LOW.value, ConfidenceLevel.UNKNOWN.value)
            ),
        }

    def _build_description(
        self,
        hedging: List[str],
        contradictions: List[str],
        score: float,
    ) -> str:
        parts = [f"Confidence: {score:.0%}"]
        if hedging:
            parts.append(f"Hedging: {', '.join(hedging[:3])}")
        if contradictions:
            parts.append(f"Contradictions: {', '.join(contradictions[:3])}")
        return "; ".join(parts)

    def _should_escalate(self, level: ConfidenceLevel, score: float) -> bool:
        if not self._require_action:
            return False
        return level in (ConfidenceLevel.LOW, ConfidenceLevel.UNKNOWN) or score < self._min_threshold


__all__ = [
    "ConfidenceLevel",
    "UncertaintyEvent",
    "UncertaintyHandler",
]
