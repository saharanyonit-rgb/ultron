"""Tests for JARVIS HTTP API Server."""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from ultron.web import EventBroadcaster, JarvisAPI, JarvisRequestHandler


def _start_server(port: int = 0) -> JarvisAPI:
    """Start a test server on a random available port."""
    server = JarvisAPI(host="127.0.0.1", port=port)
    server._start_time = time.time()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)  # Let server start
    return server


def _get_port(server: JarvisAPI) -> int:
    return server.server_address[1]


# ═══════════════════════════════════════════════════════════════════
# EventBroadcaster
# ═══════════════════════════════════════════════════════════════════

class TestEventBroadcaster:
    def test_subscribe_and_broadcast(self):
        b = EventBroadcaster()
        q = b.subscribe()
        b.broadcast("test_event", {"key": "value"})
        msg = q.get_nowait()
        assert "test_event" in msg
        assert '"key": "value"' in msg

    def test_unsubscribe(self):
        b = EventBroadcaster()
        q = b.subscribe()
        b.unsubscribe(q)
        b.broadcast("test", {})
        assert q.empty()

    def test_broadcast_to_multiple(self):
        b = EventBroadcaster()
        q1 = b.subscribe()
        q2 = b.subscribe()
        b.broadcast("ev", {"a": 1})
        assert not q1.empty()
        assert not q2.empty()


# ═══════════════════════════════════════════════════════════════════
# JarvisAPI Data Access
# ═══════════════════════════════════════════════════════════════════

class TestJarvisAPIData:
    def test_get_status(self):
        server = JarvisAPI(port=0)
        status = server.get_status()
        assert status["status"] == "running"
        assert status["orchestrator"] is False
        assert status["goals_count"] == 0

    def test_submit_and_list_goals(self):
        server = JarvisAPI(port=0)
        result = server.submit_goal({"description": "Test goal"})
        assert result["id"].startswith("goal_")
        assert result["status"] == "created"

        goals = server.list_goals()
        assert len(goals) == 1
        assert goals[0]["description"] == "Test goal"

    def test_chat_mode_uses_brain_when_orchestrator_is_available(self):
        """Dashboard chat must return a conversational response, not a plan summary."""
        brain = MagicMock()
        brain.process.return_value = SimpleNamespace(
            response="Hello from JARVIS", error=None,
            status=SimpleNamespace(name="SUCCESS"), events=[],
        )
        orchestrator = MagicMock()
        server = JarvisAPI(port=0, brain=brain, orchestrator=orchestrator)

        server.submit_goal({"description": "Hello", "mode": "chat"})
        for _ in range(100):
            if brain.process.called:
                break
            time.sleep(0.01)

        assert brain.process.called
        assert not orchestrator.execute_goal.called

    def test_get_goal(self):
        server = JarvisAPI(port=0)
        result = server.submit_goal({"description": "G1"})
        goal = server.get_goal(result["id"])
        assert goal is not None
        assert goal["description"] == "G1"

    def test_get_goal_not_found(self):
        server = JarvisAPI(port=0)
        assert server.get_goal("nonexistent") is None

    def test_list_tools_empty(self):
        server = JarvisAPI(port=0)
        assert server.list_tools() == []

    def test_control_state_no_controller(self):
        server = JarvisAPI(port=0)
        state = server.get_control_state()
        assert state["state"] == "no_controller"

    def test_pause_no_controller(self):
        server = JarvisAPI(port=0)
        result = server.pause_execution()
        assert result["status"] == "no_controller"

    def test_resume_no_controller(self):
        server = JarvisAPI(port=0)
        result = server.resume_execution()
        assert result["status"] == "no_controller"

    def test_stop_no_controller(self):
        server = JarvisAPI(port=0)
        result = server.stop_execution()
        assert result["status"] == "no_controller"


# ═══════════════════════════════════════════════════════════════════
# JarvisAPI with Mock Controller
# ═══════════════════════════════════════════════════════════════════

class TestJarvisAPIWithController:
    def test_pause_with_controller(self):
        controller = MagicMock()
        controller._state = "running"
        server = JarvisAPI(port=0, execution_controller=controller)
        result = server.pause_execution()
        assert result["status"] == "paused"
        controller.pause.assert_called_once()

    def test_resume_with_controller(self):
        controller = MagicMock()
        controller._state = "paused"
        server = JarvisAPI(port=0, execution_controller=controller)
        result = server.resume_execution()
        assert result["status"] == "resumed"
        controller.resume.assert_called_once()

    def test_stop_with_controller(self):
        controller = MagicMock()
        controller._state = "running"
        server = JarvisAPI(port=0, execution_controller=controller)
        result = server.stop_execution()
        assert result["status"] == "stopped"
        controller.emergency_stop.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# Event Broadcasting
# ═══════════════════════════════════════════════════════════════════

class TestEventBroadcasting:
    def test_broadcast_event(self):
        server = JarvisAPI(port=0)
        q = server.subscribe_events()
        server.broadcast_event("custom_event", {"data": 42})
        msg = q.get_nowait()
        assert "custom_event" in msg
        assert '"data": 42' in msg

    def test_subscribe_unsubscribe(self):
        server = JarvisAPI(port=0)
        q = server.subscribe_events()
        server.unsubscribe_events(q)
        server.broadcast_event("ev", {})
        assert q.empty()


# ═══════════════════════════════════════════════════════════════════
# HTTP Integration (using httpx)
# ═══════════════════════════════════════════════════════════════════

class TestHTTPIntegration:
    def test_status_endpoint(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/status")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "running"
        finally:
            server.shutdown()

    def test_goals_list_empty(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/goals")
            assert r.status_code == 200
            assert r.json()["goals"] == []
        finally:
            server.shutdown()

    def test_submit_goal_via_http(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.post(
                f"http://127.0.0.1:{port}/api/goals",
                json={"description": "Do something cool"},
            )
            assert r.status_code == 201
            data = r.json()
            assert data["description"] == "Do something cool"

            r2 = httpx.get(f"http://127.0.0.1:{port}/api/goals")
            assert len(r2.json()["goals"]) == 1
        finally:
            server.shutdown()

    def test_submit_goal_missing_description(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.post(f"http://127.0.0.1:{port}/api/goals", json={})
            assert r.status_code == 400
            assert "error" in r.json()
        finally:
            server.shutdown()

    def test_get_goal_not_found(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/goals/nope")
            assert r.status_code == 404
        finally:
            server.shutdown()

    def test_tools_endpoint(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/tools")
            assert r.status_code == 200
            assert "tools" in r.json()
        finally:
            server.shutdown()

    def test_control_state_endpoint(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/control")
            assert r.status_code == 200
        finally:
            server.shutdown()

    def test_dashboard_served(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/")
            assert r.status_code == 200
            assert "ULTRON" in r.text
            assert "<html" in r.text.lower()
        finally:
            server.shutdown()

    def test_404(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/api/nonexistent")
            assert r.status_code == 404
        finally:
            server.shutdown()

    def test_cors_headers(self):
        import httpx
        server = _start_server()
        port = _get_port(server)
        try:
            r = httpx.options(f"http://127.0.0.1:{port}/api/status")
            assert r.headers.get("access-control-allow-origin") == "*"
        finally:
            server.shutdown()
