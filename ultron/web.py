"""High-performance HTTP API Server for JARVIS.

Multi-threaded server with:
  - Concurrent request handling via ThreadingMixin
  - Static file caching with ETags
  - Gzip compression for large responses
  - Connection keep-alive
  - Proper timeout handling
  - SSE streaming support
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import mimetypes
import os
import queue
import socketserver
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, unquote

from ultron.web_broadcaster import EventBroadcaster
from ultron.web_static import (
    API_CACHE_CONTROL,
    FRONTEND_DIR,
    MIME_TYPES,
    STATIC_CACHE_MAX_AGE,
)
from ultron.permission_manager import PermissionManager, WebPermissionEngine
from ultron.policy import PolicyEngine

logger = logging.getLogger("ultron.web")


def _check_termux_api() -> bool:
    """Check if termux-api is available."""
    try:
        import subprocess
        result = subprocess.run(
            ["which", "termux-battery-status"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server."""
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128
    timeout = 30

    def server_activate(self) -> None:
        self.socket.listen(self.request_queue_size)
        super().server_activate()


class JarvisRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the JARVIS API and frontend."""

    server: JarvisAPI

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug(fmt, *args)

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", API_CACHE_CONTROL)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client disconnected - this is normal, just log and continue
            logger.debug("Client disconnected while sending response")

    def _send_error(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _send_file(self, file_path: Path, status: int = 200) -> None:
        """Serve a static file with caching and compression."""
        if not file_path.is_file():
            self._send_error(404, "Not found")
            return

        mime_type = MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
        body = file_path.read_bytes()

        # Generate ETag for caching
        etag = hashlib.md5(body).hexdigest()

        # Check If-None-Match header
        client_etag = self.headers.get("If-None-Match", "")
        if client_etag == etag:
            self.send_response(304)
            self.end_headers()
            return

        # Try gzip compression for text files
        accept_encoding = self.headers.get("Accept-Encoding", "")
        use_gzip = "gzip" in accept_encoding and len(body) > 1024 and mime_type.startswith(("text/", "application/javascript", "application/json"))
        if use_gzip:
            body = gzip.compress(body, compresslevel=6)

        self.send_response(status)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("ETag", etag)
        # The dashboard is served by the same local process as its API.
        # Revalidate assets so a running UI cannot keep an older chat client.
        self.send_header("Cache-Control", "no-cache")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Optional[Dict[str, Any]]:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/")

        # ── API Routes ──────────────────────────────────────────
        if path == "/api/status":
            self._handle_status()
        elif path == "/api/goals":
            self._handle_list_goals()
        elif path.startswith("/api/goals/"):
            goal_id = path.split("/")[-1]
            self._handle_get_goal(goal_id)
        elif path == "/api/tasks":
            self._handle_list_tasks()
        elif path.startswith("/api/tasks/"):
            task_id = path.split("/")[-1]
            self._handle_get_task(task_id)
        elif path == "/api/tools":
            self._handle_list_tools()
        elif path == "/api/events":
            self._handle_sse()
        elif path == "/api/control":
            self._handle_control_state()
        elif path == "/api/system/metrics":
            self._handle_system_metrics()
        elif path == "/api/system/network":
            self._handle_network_status()
        elif path == "/api/system/info":
            self._handle_system_info()
        elif path == "/api/agents":
            self._handle_agent_status()
        elif path == "/api/memory":
            self._handle_memory_status()
        elif path == "/api/security":
            self._handle_security_status()
        elif path == "/api/computer":
            self._handle_computer_state()
        elif path == "/api/orchestrator":
            self._handle_orchestrator_state()
        elif path == "/api/voice":
            self._handle_voice_state()
        elif path == "/api/vision/analyze":
            self._handle_vision_analyze()
        elif path == "/api/calendar/events":
            self._handle_calendar_list()
        elif path.startswith("/api/calendar/events/"):
            event_id = path.split("/")[-1]
            self._handle_calendar_get(event_id)
        elif path == "/api/notes":
            self._handle_notes_list()
        elif path.startswith("/api/notes/"):
            note_id = path.split("/")[-1]
            self._handle_notes_get(note_id)
        elif path == "/api/reminders":
            self._handle_reminders_list()
        elif path.startswith("/api/reminders/"):
            reminder_id = path.split("/")[-1]
            self._handle_reminders_get(reminder_id)
        elif path == "/api/permissions" or path.startswith("/api/permissions/"):
            self._handle_permission_request()
        elif path == "/api/android":
            self._handle_android_status()
        else:
            # ── Static File Serving ─────────────────────────────
            self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/goals":
            self._handle_submit_goal()
        elif path == "/api/control/pause":
            self._handle_pause()
        elif path == "/api/control/resume":
            self._handle_resume()
        elif path == "/api/control/stop":
            self._handle_stop()
        elif path == "/api/voice/speak":
            self._handle_voice_speak()
        elif path == "/api/voice/listen":
            self._handle_voice_listen()
        elif path == "/api/voice/interrupt":
            self._handle_voice_interrupt()
        elif path == "/api/execute":
            self._handle_execute_command()
        elif path == "/api/calendar/events":
            self._handle_calendar_create()
        elif path == "/api/notes":
            self._handle_notes_create()
        elif path.startswith("/api/notes/"):
            note_id = path.split("/")[-1]
            self._handle_notes_update(note_id)
        elif path == "/api/reminders":
            self._handle_reminders_create()
        elif path.startswith("/api/permissions/"):
            self._handle_permission_request()
        else:
            self._send_error(404, "Not found")

    def do_PUT(self) -> None:
        """Update a persisted resource from the dashboard."""
        path = urlparse(self.path).path.rstrip("/")
        if path.startswith("/api/notes/"):
            self._handle_notes_update(path.split("/")[-1])
        elif path.startswith("/api/calendar/events/"):
            self._handle_calendar_update(path.split("/")[-1])
        else:
            self._send_error(404, "Not found")

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/calendar/events/"):
            event_id = path.split("/")[-1]
            self._handle_calendar_delete(event_id)
        elif path.startswith("/api/notes/"):
            note_id = path.split("/")[-1]
            self._handle_notes_delete(note_id)
        elif path.startswith("/api/reminders/"):
            reminder_id = path.split("/")[-1]
            self._handle_reminders_delete(reminder_id)
        else:
            self._send_error(404, "Not found")

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Cache-Control")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    # ── Static File Serving ─────────────────────────────────────

    def _serve_static(self, path: str) -> None:
        """Serve files from the frontend directory."""
        if not FRONTEND_DIR.is_dir():
            self._send_error(404, "Frontend not found")
            return

        if path in ("", "/"):
            file_path = FRONTEND_DIR / "index.html"
        else:
            file_path = FRONTEND_DIR / path.lstrip("/")

        # Prevent directory traversal
        try:
            file_path.resolve().relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_error(403, "Forbidden")
            return

        self._send_file(file_path)

    # ── API Handlers ────────────────────────────────────────────

    def _handle_status(self) -> None:
        status = self.server.get_status()
        self._send_json(status)

    def _handle_list_goals(self) -> None:
        goals = self.server.list_goals()
        self._send_json({"goals": goals})

    def _handle_get_goal(self, goal_id: str) -> None:
        goal = self.server.get_goal(goal_id)
        if goal is None:
            self._send_error(404, f"Goal {goal_id} not found")
        else:
            self._send_json(goal)

    def _handle_list_tasks(self) -> None:
        tasks = self.server.list_tasks()
        self._send_json({"tasks": tasks})

    def _handle_get_task(self, task_id: str) -> None:
        task = self.server.get_task(task_id)
        if task is None:
            self._send_error(404, f"Task {task_id} not found")
        else:
            self._send_json(task)

    def _handle_list_tools(self) -> None:
        if hasattr(self.server, "list_tools") and callable(self.server.list_tools):
            tools = self.server.list_tools()
        else:
            tools = []
        self._send_json({"tools": tools})

    def _handle_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if hasattr(self.server, "subscribe_events") and callable(self.server.subscribe_events):
            q = self.server.subscribe_events()
        else:
            q = queue.Queue()

        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    self.wfile.write(data.encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    # Client disconnected
                    logger.debug("Client disconnected from SSE")
                    break
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if hasattr(self.server, "unsubscribe_events") and callable(self.server.unsubscribe_events):
                self.server.unsubscribe_events(q)

    def _handle_control_state(self) -> None:
        ec = getattr(self.server, "_execution_controller", None)
        curr_state = getattr(self.server, "_current_state", "idle")
        if ec:
            self._send_json({
                "state": getattr(ec, "_state", "unknown"),
                "rate_limit": {"max_per_minute": 30},
            })
        else:
            self._send_json({
                "state": curr_state,
                "rate_limit": {"max_per_minute": 30},
            })

    def _handle_submit_goal(self) -> None:
        body = self._read_body()
        if not body or "description" not in body:
            self._send_error(400, "Missing 'description' field")
            return
        if hasattr(self.server, "submit_goal") and callable(self.server.submit_goal):
            result = self.server.submit_goal(body)
        else:
            result = {"id": "goal_1", "description": body["description"], "status": "submitted"}
        self._send_json(result, 201)

    def _handle_pause(self) -> None:
        if hasattr(self.server, "pause_execution") and callable(self.server.pause_execution):
            result = self.server.pause_execution()
        else:
            result = {"status": "no_controller"}
        self._send_json(result)

    def _handle_resume(self) -> None:
        if hasattr(self.server, "resume_execution") and callable(self.server.resume_execution):
            result = self.server.resume_execution()
        else:
            result = {"status": "no_controller"}
        self._send_json(result)

    def _handle_stop(self) -> None:
        if hasattr(self.server, "stop_execution") and callable(self.server.stop_execution):
            result = self.server.stop_execution()
        else:
            result = {"status": "no_controller"}
        self._send_json(result)

    # ── Extended API Handlers ───────────────────────────────────

    def _handle_system_metrics(self) -> None:
        from ultron.web_api import get_system_metrics
        self._send_json(get_system_metrics())

    def _handle_network_status(self) -> None:
        from ultron.web_api import get_network_status
        self._send_json(get_network_status())

    def _handle_system_info(self) -> None:
        from ultron.web_api import get_system_info
        self._send_json(get_system_info())

    def _handle_agent_status(self) -> None:
        from ultron.web_api import get_agent_status
        self._send_json(get_agent_status())

    def _handle_memory_status(self) -> None:
        from ultron.web_api import get_memory_status
        self._send_json(get_memory_status())

    def _handle_security_status(self) -> None:
        from ultron.web_api import get_security_status
        self._send_json(get_security_status())

    def _handle_computer_state(self) -> None:
        from ultron.web_api import get_computer_state
        self._send_json(get_computer_state())

    def _handle_orchestrator_state(self) -> None:
        from ultron.web_api import get_orchestrator_state
        # Use the orchestrator if available, otherwise use our tracked state
        if self.server._orchestrator:
            self._send_json(get_orchestrator_state(self.server._orchestrator))
        else:
            self._send_json(self.server.get_current_state())

    # ── Voice ─────────────────────────────────────────────────────

    def _handle_voice_state(self) -> None:
        self.server._wire_voice_broadcast()
        from ultron.web_api import get_voice_state
        self._send_json(get_voice_state())

    # ── Android Status ─────────────────────────────────────────

    def _handle_android_status(self) -> None:
        try:
            from ultron.platform import is_android
            from ultron.tools import ToolRegistry
            registry = ToolRegistry()
            android_tools = [t.name for t in registry.all()
                           if any(kw in t.name for kw in [
                               'call', 'sms', 'contact', 'alarm', 'notification',
                               'battery', 'toggle', 'brightness', 'volume', 'wifi',
                               'bluetooth', 'airplane', 'data', 'dnd', 'screen_on',
                               'screen_off', 'unlock', 'device_info', 'network_info',
                               'location', 'scan_wifi', 'running_apps', 'installed',
                               'storage', 'memory', 'media', 'vibrate', 'toast',
                               'tap', 'swipe', 'long_press', 'double_tap',
                               'input_text', 'press_back', 'press_home', 'press_recent',
                               'press_key', 'drag', 'ui_dump', 'click_ui', 'read_screen',
                               'screen_resolution', 'screen_density',
                           ])]
            self._send_json({
                "is_android": is_android(),
                "android_tools": android_tools,
                "android_tool_count": len(android_tools),
                "total_tools": len(registry.all()),
                "termux_api_available": _check_termux_api(),
            })
        except Exception as e:
            self._send_json({"is_android": False, "error": str(e)})

    # ── Calendar ────────────────────────────────────────────────

    def _handle_calendar_list(self) -> None:
        from ultron.services import get_calendar_service
        service = get_calendar_service()
        query = urlparse(self.path).query
        params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
        self._send_json({"events": service.list_events(params.get("from_time"), params.get("to_time"))})

    def _handle_calendar_get(self, event_id: str) -> None:
        from ultron.services import get_calendar_service
        service = get_calendar_service()
        event = service.get_event(event_id)
        if event is None:
            self._send_error(404, f"Event {event_id} not found")
        else:
            self._send_json(event)

    def _handle_calendar_create(self) -> None:
        from ultron.services import get_calendar_service
        body = self._read_body()
        if not body or "title" not in body:
            self._send_error(400, "Missing 'title' field")
            return
        service = get_calendar_service()
        event = service.create_event(
            title=body.get("title", ""),
            start_time=body.get("start_time", ""),
            end_time=body.get("end_time"),
            description=body.get("description", ""),
            timezone=body.get("timezone", "UTC"),
            recurrence=body.get("recurrence"),
            metadata=body.get("metadata"),
        )
        self._send_json(event, 201)

    def _handle_calendar_delete(self, event_id: str) -> None:
        from ultron.services import get_calendar_service
        service = get_calendar_service()
        if service.delete_event(event_id):
            self._send_json({"deleted": True})
        else:
            self._send_error(404, f"Event {event_id} not found")

    def _handle_calendar_update(self, event_id: str) -> None:
        from ultron.services import get_calendar_service
        body = self._read_body()
        if body is None:
            self._send_error(400, "A JSON request body is required")
            return
        allowed = ("title", "description", "start_time", "end_time", "timezone", "recurrence", "metadata")
        event = get_calendar_service().update_event(event_id, **{key: body[key] for key in allowed if key in body})
        if event is None:
            self._send_error(404, f"Event {event_id} not found")
        else:
            self._send_json(event)

    # ── Notes ─────────────────────────────────────────────────

    def _handle_notes_list(self) -> None:
        from ultron.services import get_notes_service
        service = get_notes_service()
        query = urlparse(self.path).query
        params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
        self._send_json({"notes": service.list_notes(params.get("tag"))})

    def _handle_notes_get(self, note_id: str) -> None:
        from ultron.services import get_notes_service
        service = get_notes_service()
        note = service.get_note(note_id)
        if note is None:
            self._send_error(404, f"Note {note_id} not found")
        else:
            self._send_json(note)

    def _handle_notes_create(self) -> None:
        from ultron.services import get_notes_service
        body = self._read_body()
        if not body or "title" not in body:
            self._send_error(400, "Missing 'title' field")
            return
        service = get_notes_service()
        note = service.create_note(
            title=body.get("title", ""),
            content=body.get("content", ""),
            tags=body.get("tags"),
            metadata=body.get("metadata"),
        )
        self._send_json(note, 201)

    def _handle_notes_update(self, note_id: str) -> None:
        from ultron.services import get_notes_service
        body = self._read_body()
        service = get_notes_service()
        note = service.update_note(
            note_id,
            title=body.get("title") if body else None,
            content=body.get("content") if body else None,
            tags=body.get("tags") if body else None,
        )
        if note is None:
            self._send_error(404, f"Note {note_id} not found")
        else:
            self._send_json(note)

    def _handle_notes_delete(self, note_id: str) -> None:
        from ultron.services import get_notes_service
        service = get_notes_service()
        if service.delete_note(note_id):
            self._send_json({"deleted": True})
        else:
            self._send_error(404, f"Note {note_id} not found")

    # ── Reminders ─────────────────────────────────────────────

    def _handle_reminders_list(self) -> None:
        from ultron.services import get_reminders_service
        service = get_reminders_service()
        self._send_json({"reminders": service.list_reminders()})

    def _handle_reminders_get(self, reminder_id: str) -> None:
        from ultron.services import get_reminders_service
        service = get_reminders_service()
        reminder = service.get_reminder(reminder_id)
        if reminder is None:
            self._send_error(404, f"Reminder {reminder_id} not found")
        else:
            self._send_json(reminder)

    def _handle_reminders_create(self) -> None:
        from ultron.services import get_reminders_service
        body = self._read_body()
        if not body or "message" not in body:
            self._send_error(400, "Missing 'message' field")
            return
        if "trigger_time" not in body:
            self._send_error(400, "Missing 'trigger_time' field")
            return
        service = get_reminders_service()
        reminder = service.create_reminder(
            message=body.get("message", ""),
            trigger_time=body.get("trigger_time", ""),
            recurrence=body.get("recurrence"),
            metadata=body.get("metadata"),
        )
        self._send_json(reminder, 201)

    def _handle_reminders_delete(self, reminder_id: str) -> None:
        from ultron.services import get_reminders_service
        service = get_reminders_service()
        if service.delete_reminder(reminder_id):
            self._send_json({"deleted": True})
        else:
            self._send_error(404, f"Reminder {reminder_id} not found")

    def _handle_voice_speak(self) -> None:
        body = self._read_body()
        if not body or "text" not in body:
            self._send_error(400, "Missing 'text' field")
            return
        try:
            self.server._wire_voice_broadcast()
            from ultron.tools.voice import get_voice_engine
            engine = get_voice_engine()
            result = engine.speak(body["text"])
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_voice_listen(self) -> None:
        try:
            self.server._wire_voice_broadcast()
            from ultron.tools.voice import get_voice_engine
            engine = get_voice_engine()
            timeout = 10
            body = self._read_body()
            if body and "timeout" in body:
                try:
                    timeout = int(body["timeout"])
                except (TypeError, ValueError):
                    timeout = 10
            result = engine.listen(timeout=timeout)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_voice_interrupt(self) -> None:
        """Stop any in-progress TTS/STT and return the engine to idle."""
        try:
            self.server._wire_voice_broadcast()
            from ultron.tools.voice import get_voice_engine, VoiceState
            engine = get_voice_engine()
            engine.interrupt()
            self._send_json({"interrupted": True, "state": engine.state.value})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_vision_analyze(self) -> None:
        body = self._read_body() or {}
        prompt = body.get("prompt", "Describe what you see on the screen in detail.")
        path = body.get("path")
        try:
            from ultron.tools.vision import VisionTool
            tool = VisionTool()
            result = tool.run(prompt=prompt, path=path)
            if "error" in result:
                self._send_json(result, 400)
            else:
                self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ── Permissions ───────────────────────────────────────────────

    def _handle_permission_request(self) -> None:
        """Handle permission-related API requests.

        Routes:
            GET  /api/permissions              - List all pending permissions
            GET  /api/permissions/<id>        - Get specific pending permission
            POST /api/permissions/<id>/allow  - Allow a permission
            POST /api/permissions/<id>/deny   - Deny a permission
        """
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Extract permission ID if present
        parts = path.split("/")
        permission_id = None
        if len(parts) >= 4 and parts[2] == "permissions":
            permission_id = parts[3]

        if self.command == "GET":
            if permission_id:
                # Get specific permission
                pending = self.server._permission_manager.get_pending(permission_id)
                if pending is None:
                    self._send_error(404, f"Permission {permission_id} not found")
                else:
                    self._send_json(pending)
            else:
                # List all pending
                self._send_json({
                    "pending": self.server._permission_manager.list_pending()
                })
        elif self.command == "POST":
            if permission_id:
                # Parse action from path
                if path.endswith("/allow"):
                    allowed = True
                elif path.endswith("/deny"):
                    allowed = False
                else:
                    self._send_error(400, "Invalid permission action. Use /allow or /deny")
                    return

                success = self.server._permission_manager.decide(permission_id, allowed)
                if success:
                    self._send_json({
                        "permission_id": permission_id,
                        "decision": "allowed" if allowed else "denied",
                        "accepted": True
                    })
                else:
                    self._send_json({
                        "permission_id": permission_id,
                        "decision": "allowed" if allowed else "denied",
                        "accepted": False,
                        "error": "Permission request not found or expired"
                    }, 404)
            else:
                self._send_error(400, "Permission ID required")
        else:
            self._send_error(405, "Method not allowed")

    def _handle_execute_command(self) -> None:
        body = self._read_body()
        if not body or "command" not in body:
            self._send_error(400, "Missing 'command' field")
            return
        try:
            from ultron.tools.execute import ExecuteCommand
            tool = ExecuteCommand()
            try:
                timeout = int(body.get("timeout", 60))
            except (TypeError, ValueError):
                timeout = 60
            working_dir = body.get("working_directory")
            result = tool.run(
                command=body["command"],
                timeout=timeout,
                working_directory=working_dir,
            )
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


class BrainExecutionController:
    """Wraps the Brain for pause/resume/stop control via the web API."""

    def __init__(self, brain):
        self._brain = brain
        self._state = "idle"
        self._paused = False
        self._stopped = False

    @property
    def state(self):
        return self._state

    def pause(self):
        self._paused = True
        self._state = "waiting"

    def resume(self):
        self._paused = False
        self._state = "executing"

    def emergency_stop(self):
        self._stopped = True
        self._state = "idle"


_STATUS_TO_SSE: Dict[str, str] = {
    "planning": "planning",
    "plan_created": "plan_created",
    "task_started": "task_started",
    "agent_selected": "agent_selected",
    "step_started": "step_started",
    "step_completed": "step_completed",
    "step_failed": "step_failed",
    "verifying": "verifying",
    "verified": "verified",
    "retrying": "retrying",
    "recovering": "recovering",
    "replaning": "replaning",
    "completed": "completed",
    "failed": "failed",
    "error": "error",
    # Brain orchestration events
    "brain_routing": "brain_routing",
    "agent.selected": "agent.selected",
    "agent.started": "agent.started",
    "agent.progress": "agent.progress",
    "agent.completed": "agent.completed",
    "agent.failed": "agent.failed",
    "verification.started": "verification.started",
    "verification.completed": "verification.completed",
    "replan.started": "replan.started",
    "replan.completed": "replan.completed",
    "brain_error": "brain_error",
}


class OrchestratorEventBridge:
    """Bridges StatusReporter events → SSE broadcaster for frontend consumption."""

    def __init__(self, status_reporter: Any, broadcaster: EventBroadcaster) -> None:
        self._reporter = status_reporter
        self._broadcaster = broadcaster
        from ultron.status import CallbackSubscriber, StatusUpdate
        self._subscriber = CallbackSubscriber(self._on_status)
        self._reporter.subscribe(self._subscriber)

    def _on_status(self, update: StatusUpdate) -> None:
        event_name = _STATUS_TO_SSE.get(update.event.value, update.event.value)
        self._broadcaster.broadcast(event_name, update.to_dict())

    def close(self) -> None:
        self._reporter.unsubscribe(self._subscriber)


class JarvisAPI(ThreadedHTTPServer):
    """Multi-threaded HTTP server for the JARVIS API.

    Provides routes for goal management, task status, tool listing,
    execution control, SSE event streaming, and system telemetry.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        orchestrator: Optional[Any] = None,
        execution_controller: Optional[Any] = None,
        brain: Optional[Any] = None,
        registry: Optional[Any] = None,
        memory: Optional[Any] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._brain = brain
        self._registry = registry
        self._memory = memory
        self._execution_controller = execution_controller
        self._event_broadcaster = EventBroadcaster()
        self._orchestrator_bridge: Optional[OrchestratorEventBridge] = None
        self._permission_manager = PermissionManager(broadcaster=self._event_broadcaster)
        self._goals: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="jarvis-exec")
        self._current_state = "idle"
        self._execution_count = 0

        super(JarvisAPI, self).__init__((host, port), JarvisRequestHandler)
        logger.info("JARVIS API server initialized on %s:%d", host, port)

    def get_current_state(self) -> Dict[str, Any]:
        """Return current execution state for the frontend."""
        return {
            "state": self._current_state,
            "online": True,
            "execution_count": self._execution_count,
            "brain_active": self._brain is not None,
            "orchestrator_active": self._orchestrator is not None,
        }

    def set_orchestrator(self, orchestrator: Any) -> None:
        """Set or update the orchestrator after server construction."""
        self._orchestrator = orchestrator
        if orchestrator is not None:
            self._orchestrator_bridge = OrchestratorEventBridge(
                orchestrator._status, self._event_broadcaster
            )
            # Wire up brain orchestrator events to SSE if brain orchestrator is available
            if hasattr(orchestrator, "_brain_orchestrator") and orchestrator._brain_orchestrator is not None:
                def brain_event_handler(event_type: str, data: Dict[str, Any]) -> None:
                    self._event_broadcaster.broadcast(event_type, data)
                orchestrator._brain_orchestrator._event_handler = brain_event_handler
                # Also update orchestrator's brain_event_handler reference if it has one
                if hasattr(orchestrator, "_brain_event_handler") and orchestrator._brain_event_handler:
                    # Chain the handlers
                    original_handler = orchestrator._brain_event_handler
                    def chained_handler(event_type: str, data: Dict[str, Any]) -> None:
                        original_handler(event_type, data)
                        brain_event_handler(event_type, data)
                    orchestrator._brain_orchestrator._event_handler = chained_handler
                logger.info("Brain orchestrator connected to SSE event broadcaster")
            # Wire up permission manager to orchestrator's policy engine
            if hasattr(orchestrator, "_policy_engine") and orchestrator._policy_engine is not None:
                orchestrator._policy_engine = WebPermissionEngine(
                    orchestrator._policy_engine, self._permission_manager
                )
            logger.info("Orchestrator connected to SSE event broadcaster")

    # ── Data Access ────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "running",
            "provider": os.environ.get("ULTRON_PROVIDER", "gemini"),
            "orchestrator": self._orchestrator is not None,
            "execution_controller": self._execution_controller is not None,
            "goals_count": len(self._goals),
            "tasks_count": len(self._tasks),
            "uptime_seconds": time.time() - self._start_time if hasattr(self, "_start_time") else 0,
        }

    def list_goals(self) -> List[Dict[str, Any]]:
        return list(self._goals.values())

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        return self._goals.get(goal_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    def list_tools(self) -> List[Dict[str, Any]]:
        if self._registry is not None and hasattr(self._registry, "_tools"):
            return [
                {"name": name, "description": getattr(tool, "description", "")}
                for name, tool in self._registry._tools.items()
            ]
        if self._orchestrator and hasattr(self._orchestrator, "_tool_executor"):
            executor = self._orchestrator._tool_executor
            if hasattr(executor, "_registry"):
                registry = executor._registry
                if hasattr(registry, "_tools"):
                    return [
                        {"name": name, "description": getattr(t, "description", "")}
                        for name, t in registry._tools.items()
                    ]
        return []

    def get_control_state(self) -> Dict[str, Any]:
        if self._execution_controller:
            return {
                "state": getattr(self._execution_controller, "_state", "unknown"),
                "rate_limit": {"max_per_minute": 30},
            }
        return {"state": "no_controller", "rate_limit": {}}

    def _wire_voice_broadcast(self) -> None:
        """Connect voice engine state changes to the SSE broadcaster."""
        try:
            from ultron.tools.voice import get_voice_engine, VoiceState

            def _on_voice_state(state: VoiceState) -> None:
                self._event_broadcaster.broadcast("voice_state", {"state": state.value, "available": True})

            engine = get_voice_engine()
            # Only set if not already wired to a broadcaster
            if getattr(engine, "_on_state_change", None) is None or getattr(engine, "_broadcast_wired", False) is False:
                engine.set_state_callback(_on_voice_state)
                engine._broadcast_wired = True
        except Exception as e:
            logger.debug("Could not wire voice broadcast: %s", e)

    # ── Actions ────────────────────────────────────────────────────

    def submit_goal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        goal_id = f"goal_{len(self._goals) + 1}"
        goal = {
            "id": goal_id,
            "description": data["description"],
            "status": "created",
            "created_at": time.time(),
        }
        self._goals[goal_id] = goal
        self._event_broadcaster.broadcast("goal_created", goal)

        # A user message is conversational by default. Autonomous planning
        # is opt-in; otherwise simple chat such as "hi" must reach the LLM.
        if self._brain and data.get("mode") != "goal":
            self._execute_goal_async(goal_id, data["description"])
        elif self._orchestrator:
            self._execute_via_orchestrator(goal_id, data["description"])
        elif self._brain:
            self._execute_goal_async(goal_id, data["description"])

        return goal

    def _execute_via_orchestrator(self, goal_id: str, description: str) -> None:
        """Execute a goal through the Phase 5 Orchestrator in a background thread."""
        def _run():
            try:
                self._current_state = "planning"
                self._execution_count += 1

                goal = self._goals.get(goal_id)
                if goal:
                    goal["status"] = "planning"

                result = self._orchestrator.execute_goal(description)

                goal = self._goals.get(goal_id)
                if not goal:
                    return

                gr = result.goal_result
                if gr.outcome.value in ("success",):
                    goal["status"] = "completed"
                    goal["response"] = gr.summary
                    self._current_state = "completed"
                    self._event_broadcaster.broadcast("completed", {
                        "id": goal_id,
                        "response": gr.summary,
                        "outcome": gr.outcome.value,
                    })
                else:
                    goal["status"] = "failed"
                    goal["error"] = gr.summary
                    self._current_state = "error"
                    self._event_broadcaster.broadcast("failed", {
                        "id": goal_id,
                        "message": gr.summary,
                        "error": gr.summary,
                        "outcome": gr.outcome.value,
                    })

                time.sleep(0.5)
                self._current_state = "idle"

            except Exception as e:
                err = str(e) or f"Unhandled {type(e).__name__}"
                logger.error("Orchestrator execution failed for goal %s: %s", goal_id, err)
                self._current_state = "error"
                goal = self._goals.get(goal_id)
                if goal:
                    goal["status"] = "failed"
                    goal["error"] = err
                self._event_broadcaster.broadcast("error", {"error": err})
                self._event_broadcaster.broadcast("failed", {"error": err, "id": goal_id})
                time.sleep(1)
                self._current_state = "idle"

        self._executor.submit(_run)

    def _execute_goal_async(self, goal_id: str, description: str) -> None:
        """Execute a goal through the Brain in a background thread."""
        def _run():
            try:
                goal = self._goals.get(goal_id)
                if goal:
                    goal["status"] = "planning"

                self._current_state = "planning"
                self._execution_count += 1

                # Emit planning state
                self._event_broadcaster.broadcast("planning", {"description": "Analyzing request..."})
                # Small delay to let frontend process planning event
                time.sleep(0.3)

                if goal:
                    goal["status"] = "executing"
                self._current_state = "executing"
                self._event_broadcaster.broadcast("task_started", {
                    "id": goal_id,
                    "description": description
                })
                self._event_broadcaster.broadcast("planning", {})  # End planning

                result = self._brain.process(description)

                # Emit verifying state
                self._current_state = "verifying"
                self._event_broadcaster.broadcast("verifying", {"description": "Validating results..."})

                goal = self._goals.get(goal_id)
                if goal:
                    if result.error and result.status.name == "FAILURE":
                        goal["status"] = "failed"
                        goal["error"] = result.error
                        self._current_state = "error"
                        self._event_broadcaster.broadcast("failed", {
                            "id": goal_id,
                            "error": result.error,
                            "message": result.response or result.error
                        })
                    else:
                        goal["status"] = "completed"
                        goal["response"] = result.response
                        self._current_state = "completed"
                        self._event_broadcaster.broadcast("completed", {
                            "id": goal_id,
                            "response": result.response
                        })

                # Broadcast execution events from the brain
                for event in (result.events if result else []):
                    self._event_broadcaster.broadcast("step_completed", {
                        "message": f"Executed {event.name}" + (f" ({event.arguments})" if getattr(event, 'arguments', None) else ""),
                        "description": f"{event.name}",
                        "arguments": str(event.arguments) if getattr(event, 'arguments', None) else ""
                    })

                self._event_broadcaster.broadcast("verifying", {})  # End verifying

                # Reset to idle after a moment
                time.sleep(0.5)
                self._current_state = "idle"

            except Exception as e:
                err = str(e) or f"Unhandled {type(e).__name__}"
                logger.error("Goal execution failed: %s", err)
                self._current_state = "error"
                goal = self._goals.get(goal_id)
                if goal:
                    goal["status"] = "failed"
                    goal["error"] = err
                self._event_broadcaster.broadcast("error", {"error": err})
                self._event_broadcaster.broadcast("failed", {"error": err})
                time.sleep(1)
                self._current_state = "idle"

        self._executor.submit(_run)

    def pause_execution(self) -> Dict[str, Any]:
        if self._execution_controller and hasattr(self._execution_controller, "pause"):
            self._execution_controller.pause()
            self._event_broadcaster.broadcast("execution_paused", {})
            return {"status": "paused"}
        return {"status": "no_controller"}

    def resume_execution(self) -> Dict[str, Any]:
        if self._execution_controller and hasattr(self._execution_controller, "resume"):
            self._execution_controller.resume()
            self._event_broadcaster.broadcast("execution_resumed", {})
            return {"status": "resumed"}
        return {"status": "no_controller"}

    def stop_execution(self) -> Dict[str, Any]:
        if self._execution_controller and hasattr(self._execution_controller, "emergency_stop"):
            self._execution_controller.emergency_stop()
            self._event_broadcaster.broadcast("execution_stopped", {})
            return {"status": "stopped"}
        return {"status": "no_controller"}

    # ── Events ─────────────────────────────────────────────────────

    def subscribe_events(self) -> queue.Queue:
        return self._event_broadcaster.subscribe()

    def unsubscribe_events(self, q: queue.Queue) -> None:
        self._event_broadcaster.unsubscribe(q)

    def broadcast_event(self, event: str, data: Any) -> None:
        self._event_broadcaster.broadcast(event, data)

    def start(self, daemon: bool = True) -> None:
        """Start the server in a background thread."""
        self._start_time = time.time()
        thread = threading.Thread(target=self.serve_forever, daemon=daemon)
        thread.start()
        logger.info("JARVIS API server started in background")
        return thread


__all__ = [
    "EventBroadcaster",
    "JarvisAPI",
    "JarvisRequestHandler",
]
