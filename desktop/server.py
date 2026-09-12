"""In-process ULTRON backend server for the JARVIS desktop application.

Initializes the ULTRON backend (JarvisAPI) directly in-process, avoiding
subprocess management complexity. The backend runs in a daemon thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger("jarvis.desktop.server")


class InProcessBackend:
    """Runs the ULTRON backend in the same process as the desktop shell."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._server: Optional[object] = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._running and self._server is not None

    def start(self) -> bool:
        """Start the backend server in a daemon thread."""
        with self._lock:
            if self._running:
                logger.warning("Backend already running")
                return True

            try:
                self._server = self._build_server()
            except Exception as e:
                logger.error(f"Failed to initialize backend: {e}", exc_info=True)
                return False

            try:
                self._server.start(daemon=True)
                self._running = True
                logger.info(f"Backend started at {self.url}")
                return True
            except Exception as e:
                logger.error(f"Failed to start backend server: {e}", exc_info=True)
                return False

    def _build_server(self):
        """Build the JarvisAPI server with all dependencies wired."""
        from ultron.config import load_config
        from ultron.llm import build_provider
        from ultron.tools import ToolRegistry
        from ultron.audit import AuditLogger
        from ultron.actions.audit_log import AuditLog
        from ultron.actions import PermissionGate
        from ultron.core.agent import Agent
        from ultron.core.brain import Brain

        config = load_config()

        # Override host/port from desktop config
        import os
        if os.environ.get("JARVIS_HOST"):
            self.host = os.environ["JARVIS_HOST"]
        if os.environ.get("JARVIS_PORT"):
            self.port = int(os.environ["JARVIS_PORT"])

        # Build provider
        provider = build_provider(config)
        if provider is None:
            raise RuntimeError("Failed to initialize model provider")

        # Build tool registry (registers ALL_TOOLS automatically)
        registry = ToolRegistry()

        # Build audit
        audit = AuditLogger(config.audit_log_path)
        agent_audit = AuditLog(config.audit_log_path)

        # Build permission gate (web-friendly, allows remote decisions)
        from ultron.permission_manager import WebPermissionEngine
        from ultron.policy import PolicyEngine

        gate = PermissionGate()

        # Build agent
        agent = Agent(
            provider=provider,
            tools=registry.all(),
            audit_log=agent_audit,
            gate=gate,
            max_iterations=config.max_tool_iterations,
        )

        # Build memory
        from ultron.memory import Memory
        from ultron.memory.semantic import SemanticMemory
        from ultron.services import get_memory_service

        if str(config.memory_file):
            memory: Memory = SemanticMemory(config.memory_file)
        else:
            memory = Memory()
        get_memory_service().set_engine(memory if isinstance(memory, SemanticMemory) else None)

        # Build brain
        brain = Brain(agent=agent, memory=memory)

        # Build web server with orchestrator
        from ultron.web import JarvisAPI, BrainExecutionController
        from ultron.orchestrator import Orchestrator, OrchestratorConfig
        from ultron.autonomous import AutonomousExecutor, AutonomousConfig
        from ultron.tools import ToolExecutor
        from ultron.agent_manager import AgentManager
        from ultron.status import StatusReporter
        from ultron.brains import BrainOrchestrator

        execution_controller = BrainExecutionController(brain)

        tool_executor = ToolExecutor(registry)
        status_reporter = StatusReporter()
        agent_manager = AgentManager()

        # Create BrainOrchestrator for specialized brain processing
        brain_orchestrator = BrainOrchestrator(
            config=config,
            tools=registry.all(),
            tool_executor=tool_executor,
            event_handler=None,
            max_agent_transitions=10,
            max_retries=3,
        )

        autonomous_executor = AutonomousExecutor(
            provider=provider,
            tools=registry.all(),
            tool_executor=tool_executor,
            audit_logger=audit,
            config=AutonomousConfig(),
        )

        orchestrator = Orchestrator(
            tool_executor=tool_executor,
            agent_manager=agent_manager,
            config=OrchestratorConfig(),
            audit_logger=audit,
            status_reporter=status_reporter,
            policy_engine=None,
            risk_classifier=None,
            autonomous_executor=autonomous_executor,
            brain_orchestrator=brain_orchestrator,
        )

        server = JarvisAPI(
            host=self.host,
            port=self.port,
            orchestrator=orchestrator,
            execution_controller=execution_controller,
            brain=brain,
            registry=registry,
            memory=memory,
        )
        server.set_orchestrator(orchestrator)

        # Wire reminder notifications to SSE broadcaster
        from ultron.services import get_reminders_service
        reminders_svc = get_reminders_service()
        reminders_svc.set_notification_callback(
            lambda r: server.broadcast_event("reminder_fired", r.to_dict())
        )

        return server

    def stop(self) -> None:
        """Stop the backend server."""
        with self._lock:
            if not self._running:
                return

            try:
                self._server.shutdown()
                logger.info("Backend stopped")
            except Exception as e:
                logger.error(f"Error stopping backend: {e}")

            self._running = False

    def get_status_info(self) -> dict:
        """Get backend status information."""
        return {
            "status": "running" if self._running else "stopped",
            "port": self.port,
            "host": self.host,
            "url": self.url,
            "is_running": self.is_running,
        }