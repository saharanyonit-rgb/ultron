"""SSE Event Broadcaster for JARVIS Web Server.

Manages active Server-Sent Events (SSE) subscriptions and broadcasts
events using a thread-safe fan-out pattern.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any, List

logger = logging.getLogger("ultron.web_broadcaster")


class EventBroadcaster:
    """SSE event broadcaster using a thread-safe fan-out pattern."""

    def __init__(self) -> None:
        self._subscribers: List[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast(self, event: str, data: Any) -> None:
        payload = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
        dead: List[queue.Queue] = []
        with self._lock:
            for sub in self._subscribers:
                try:
                    sub.put_nowait(payload)
                except queue.Full:
                    dead.append(sub)
            for d in dead:
                self._subscribers.remove(d)


__all__ = ["EventBroadcaster"]
