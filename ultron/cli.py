"""Ultron terminal CLI — `python -m ultron` or the `ultron` console script.

Text in / text out. This is the temporary frontend; the orchestration brain
(`core.brain.Brain`) is UI-agnostic and is what a voice layer will reuse.
"""

from __future__ import annotations

import sys
from typing import Optional

from ultron.actions import PermissionGate
from ultron.audit import AuditLogger
from ultron.actions.permissions import CLIPermissionGate, SecurePermissionGate
from ultron.config import ConfigError, load_config
from ultron.core.agent import Agent
from ultron.core.brain import Brain, ResponseStatus
from ultron.llm import build_provider
from ultron.logging_setup import configure_logging, get_logger
from ultron.memory import Memory
from ultron.tools import ToolRegistry

BANNER = r"""\033[32m
   __         ______     ____  ____   __    _  _
  / /  ___   / ____/  __/ __ \/_  /  / /   / |/ /
 / /__/ _ \ / __/ | / / /_/ / / /  / /   /    /
/____/\___//____/|__/ \___\_/ /_/  /_/   /_/|_|
\033[0m JARVIS - Personal AI System v0.1.0
 Commands: /help  /tools  /history  /clear  /permissions  /memory  /exit
 Web UI: http://127.0.0.1:8080 (auto-opened)
"""

HELP = """Commands:
  /tools        list the V1 tools and their schemas
  /history      show this session's conversation
  /clear        forget the current conversation
  /permissions  show or toggle permission mode
  /memory       show memory persistence status
  /exit         quit (Ctrl+C also works)

Bare exit commands: exit | quit | shutdown

Just type normally to talk to Ultron. Actions it takes are written to the
audit log.
"""

logger = get_logger("ultron.cli")


class Cli:
    def __init__(
        self,
        agent: Agent,
        memory: Memory,
        registry: ToolRegistry,
        brain: Optional[Brain] = None,
    ) -> None:
        self._memory = memory
        self._registry = registry
        self._brain = brain or Brain(agent=agent, memory=memory)
        self._agent = self._brain.agent

    def repl(self) -> int:
        print(BANNER)
        while True:
            try:
                line = input("\nultron> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            code = self._dispatch(line)
            if code is False:
                break

        return 0

    def _dispatch(self, line: str):
        # Bare exit commands (spec: exit | quit | shutdown)
        if line in ("/exit", "/quit", "exit", "quit", "shutdown"):
            return False
        if line == "/help":
            print(HELP)
            return
        if line == "/tools":
            self._print_tools()
            return
        if line == "/history":
            self._print_history()
            return
        if line == "/clear":
            self._memory.clear()
            print("Conversation cleared.")
            return
        if line == "/permissions":
            self._print_permissions()
            return
        if line == "/memory":
            self._print_memory_status()
            return
        if line.startswith("/"):
            print(f"Unknown command: {line} (try /help)")
            return
        self._run(line)

    def _run(self, line: str) -> None:
        res = self._brain.process(line)
        for event in res.events:
            if event.name == "__limit__":
                print("  [limit] tool iteration limit reached")
                continue
            status = "denied" if not event.allowed else "ran"
            print(f"  [{status}] {event.name} {event.arguments}")
        if res.error and res.status == ResponseStatus.FAILURE:
            print(f"[error] {res.error}")
        else:
            print(res.response or "(no text)")

    def _print_tools(self) -> None:
        for spec in self._registry.specs():
            print(f"\n{spec.name} — {spec.description}")
            print(f"  in:  {spec.parameters.get('properties', {})}")
            print(f"  out: {spec.output_schema.get('properties', {})}")

    def _print_history(self) -> None:
        if not self._memory.all():
            print("(empty)")
            return
        for turn in self._memory.all():
            label = "you" if turn.role == "user" else "ultron"
            print(f"\n[{label}] {turn.content}")

    def _print_permissions(self) -> None:
        gate = self._brain.agent._gate
        from ultron.actions.permissions import SecurePermissionGate
        if isinstance(gate, SecurePermissionGate):
            print("Permission mode: SECURE (mutating tools require confirmation)")
        else:
            print("Permission mode: PASS-THROUGH (all tools allowed, V1 default)")
        print("Set ULTRON_REQUIRE_PERMISSION=true to enable secure mode.")

    def _print_memory_status(self) -> None:
        turns = len(self._memory)
        print(f"In-memory turns: {turns}")
        from ultron.memory.persistent import PersistentMemory
        if isinstance(self._memory, PersistentMemory):
            print(f"Persistent file: {self._memory.path}")
            if self._memory.path.is_file():
                size = self._memory.path.stat().st_size
                print(f"File size: {size} bytes")
            else:
                print("File: not yet created")
            sessions = self._memory.sessions()
            print(f"Sessions on disk: {len(sessions)}")
        else:
            print("Persistence: disabled (using in-memory only)")
            print("Set ULTRON_MEMORY_FILE to enable persistence.")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Ultron — JARVIS-style desktop assistant")
    parser.add_argument("--web", action="store_true", default=True, help="Start the web dashboard (default: on)")
    parser.add_argument("--no-web", action="store_true", help="Disable web dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Web dashboard port (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Web dashboard host (default: 127.0.0.1)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress log output")
    parser.add_argument(
        "--provider",
        choices=["gemini", "nvidia", "openrouter", "grok"],
        default=None,
        help="AI provider to use (default: from ULTRON_PROVIDER env or .env)",
    )
    args = parser.parse_args(argv)

    if args.no_web:
        args.web = False

    if args.provider:
        import os
        os.environ["ULTRON_PROVIDER"] = args.provider

    try:
        config = load_config()
    except ConfigError as exc:
        configure_logging("WARNING")
        logger.error("Configuration error: %s", exc)
        print(f"Configuration error: {exc}")
        return 1

    configure_logging("WARNING" if args.quiet else getattr(config, "log_level", "INFO"))
    logger.info("Ultron startup [provider=%s, model=%s]", config.provider, config.model)

    try:
        provider = build_provider(config)
    except Exception as exc:
        logger.error("Failed to initialize model provider: %s", exc)
        print(f"Failed to initialize the model provider: {type(exc).__name__}: {exc}")
        return 1

    registry = ToolRegistry()
    audit = AuditLogger(config.audit_log_path)
    from ultron.actions.audit_log import AuditLog
    agent_audit = AuditLog(config.audit_log_path)

    if config.require_permission:
        gate: PermissionGate = CLIPermissionGate()
    else:
        gate = PermissionGate()

    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=agent_audit,
        gate=gate,
        max_iterations=config.max_tool_iterations,
    )

    from ultron.memory.persistent import PersistentMemory
    if str(config.memory_file):
        memory: Memory = PersistentMemory(config.memory_file)
    else:
        memory = Memory()

    brain = Brain(agent=agent, memory=memory)

    web_server = None
    if args.web:
        import webbrowser
        import time as _time
        from ultron.web import JarvisAPI, BrainExecutionController
        from ultron.orchestrator import Orchestrator, OrchestratorConfig
        from ultron.autonomous import AutonomousExecutor, AutonomousConfig
        from ultron.tools import ToolExecutor
        from ultron.agent_manager import AgentManager
        from ultron.status import StatusReporter
        from ultron.audit import AuditLogger as UltrAuditLogger
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

        web_server = JarvisAPI(
            host=args.host,
            port=args.port,
            orchestrator=orchestrator,
            execution_controller=execution_controller,
            brain=brain,
            registry=registry,
            memory=memory,
        )
        web_server.set_orchestrator(orchestrator)

        # Wire reminder notifications → SSE broadcaster
        from ultron.services import get_reminders_service, ReminderStatus
        reminders_svc = get_reminders_service()
        reminders_svc.set_notification_callback(
            lambda r: web_server.broadcast_event("reminder_fired", r.to_dict())
        )

        web_server.start(daemon=True)
        url = f"http://{args.host}:{args.port}"
        print(f"Dashboard: {url}")
        def _open_browser():
            _time.sleep(1.0)
            try:
                import sys
                if sys.platform == "win32":
                    chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                    browser = webbrowser.get(f'"{chrome_path}" --app=%s')
                    browser.open_new(url)
                else:
                    webbrowser.open(url)
            except Exception:
                webbrowser.open(url)
        import threading
        threading.Thread(target=_open_browser, daemon=True).start()

    cli = Cli(agent=agent, memory=memory, registry=registry, brain=brain)
    try:
        return cli.repl()
    finally:
        logger.info("Ultron shutdown [turns=%d]", len(memory))
        if web_server:
            web_server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
