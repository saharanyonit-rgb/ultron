"""Observability and Tracing for JARVIS Phase 5.

Distributed tracing, structured logging, and metrics collection
for understanding autonomous execution behavior.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.observability")


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """A single trace span."""
    span_id: str = ""
    trace_id: str = ""
    parent_id: str = ""
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = SpanStatus.OK.value
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def finish(self, status: str = SpanStatus.OK.value) -> None:
        self.end_time = time.time()
        self.status = status

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class Trace:
    """A complete trace containing multiple spans."""
    trace_id: str = ""
    spans: List[Span] = field(default_factory=list)
    goal_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "goal_id": self.goal_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "spans": [s.to_dict() for s in self.spans],
        }


class TraceCollector:
    """Collects and manages execution traces."""

    def __init__(self, max_traces: int = 100) -> None:
        self._traces: Dict[str, Trace] = {}
        self._current_trace: Optional[Trace] = None
        self._current_span: Optional[Span] = None
        self._max_traces = max_traces

    def start_trace(self, trace_id: str, goal_id: str = "") -> Trace:
        """Start a new trace."""
        trace = Trace(trace_id=trace_id, goal_id=goal_id)
        self._traces[trace_id] = trace
        self._current_trace = trace

        if len(self._traces) > self._max_traces:
            oldest = sorted(self._traces.keys())[0]
            del self._traces[oldest]

        return trace

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span within a trace."""
        import hashlib
        span_id = hashlib.md5(
            f"{name}:{time.time()}".encode()
        ).hexdigest()[:12]

        tid = trace_id or (self._current_trace.trace_id if self._current_trace else "")
        span = Span(
            span_id=span_id,
            trace_id=tid,
            parent_id=parent_id or (self._current_span.span_id if self._current_span else ""),
            name=name,
            attributes=attributes or {},
        )

        if self._current_trace:
            self._current_trace.spans.append(span)

        self._current_span = span
        return span

    def end_span(self, status: str = SpanStatus.OK.value) -> None:
        """End the current span."""
        if self._current_span:
            self._current_span.finish(status)
            if self._current_span.parent_id:
                for s in (self._current_trace.spans if self._current_trace else []):
                    if s.span_id == self._current_span.parent_id:
                        self._current_span = s
                        return
            self._current_span = None

    def end_trace(self) -> None:
        """End the current trace."""
        if self._current_trace:
            self._current_trace.end_time = time.time()
            self._current_trace = None
            self._current_span = None

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self._traces.get(trace_id)

    def get_all_traces(self) -> List[Trace]:
        return list(self._traces.values())

    def get_trace_summary(self, trace_id: str) -> Dict[str, Any]:
        """Get a summary of a trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            return {}

        return {
            "trace_id": trace.trace_id,
            "goal_id": trace.goal_id,
            "span_count": len(trace.spans),
            "duration_ms": trace.duration_ms,
            "status": "ok" if all(
                s.status == SpanStatus.OK.value for s in trace.spans
            ) else "error",
        }


class MetricsCollector:
    """Collects execution metrics."""

    def __init__(self) -> None:
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def record_histogram(self, name: str, value: float) -> None:
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k)
                for k in self._histograms
            },
        }

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class BrainEventType(str, Enum):
    AGENT_SELECTED = "agent.selected"
    AGENT_STARTED = "agent.started"
    AGENT_PROGRESS = "agent.progress"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    VERIFICATION_STARTED = "verification.started"
    VERIFICATION_COMPLETED = "verification.completed"
    REPLAN_STARTED = "replan.started"
    REPLAN_COMPLETED = "replan.completed"


@dataclass
class BrainEvent:
    """A brain orchestration event for SSE broadcasting."""

    event_type: str
    brain_type: str = ""
    task_id: str = ""
    goal_id: str = ""
    status: str = ""
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "brain_type": self.brain_type,
            "task_id": self.task_id,
            "goal_id": self.goal_id,
            "status": self.status,
            "message": self.message,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class BrainEventCollector:
    """Collects and manages brain orchestration events."""

    def __init__(self, max_events: int = 1000) -> None:
        self._events: List[BrainEvent] = []
        self._max_events = max_events

    def add_event(self, event: BrainEvent) -> None:
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    def get_events(
        self,
        goal_id: Optional[str] = None,
        brain_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[BrainEvent]:
        filtered = self._events

        if goal_id:
            filtered = [e for e in filtered if e.goal_id == goal_id]
        if brain_type:
            filtered = [e for e in filtered if e.brain_type == brain_type]

        return filtered[-limit:]

    def clear(self) -> None:
        self._events.clear()


__all__ = [
    "SpanStatus",
    "Span",
    "Trace",
    "TraceCollector",
    "MetricsCollector",
    "BrainEventType",
    "BrainEvent",
    "BrainEventCollector",
]
