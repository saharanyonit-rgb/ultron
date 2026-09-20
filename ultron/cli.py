"""Ultron terminal CLI — `python -m ultron` or the `ultron` console script.

Text in / text out. This is the temporary frontend; the orchestration brain
(`core.brain.Brain`) is UI-agnostic and is what a voice layer will reuse.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from pathlib import Path
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
 Commands: /help  /tools  /engines  /history  /clear  /permissions  /memory  /exit
 Web UI: http://127.0.0.1:8080 (auto-opened)
 Android: run with --lan to access from your phone on the same WiFi
"""

HELP = """Commands:
  /tools        list the V1 tools and their schemas
  /engines      status + how to start Vane & AgenticSeek (external AI engines)
  /history      show this session's conversation
  /clear        forget the current conversation
  /permissions  show or toggle permission mode
  /memory       show memory persistence status
  /exit         quit (Ctrl+C also works)

Bare exit commands: exit | quit | shutdown

Just type normally to talk to Ultron. Actions it takes are written to the
audit log.
"""

ENGINES = """External engines available to JARVIS as tools:

  vane_search  (tool: vane_search)      Perplexity-style cited-source answers
    Run:  cd Vane && docker compose up -d
    Then: open http://localhost:3000 and complete setup (add a chat model +
          an embedding model: Ollama, OpenAI, Gemini, Groq, or Anthropic).
    Port: 3000 (3600 = OLLAMA)

  agenticseek_task  (tool: agenticseek_task)   Manus-style autonomous multi-agent
    Run:  cd agenticSeek && copy .env.example .env  then set WORK_DIR in .env
          docker compose up        (or: ./start_services.sh)
    Needs: Ollama on :11434 OR one of OPENAI_API_KEY / OPENROUTER_API_KEY /
          DEEPSEEK_API_KEY / GOOGLE_API_KEY (set in .env). First run downloads
          the router model — be patient.
    Port: 7777

Tips:
  - Override URLs with VANE_BASE_URL / AGENTICSEEK_BASE_URL env vars.
  - Secure AgenticSeek with AGENTICSEEK_API_TOKEN (bearer) — it can run code.
  - Both are optional: JARVIS works fully without them.
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
        if line == "/engines":
            self._print_engines()
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

    def _print_engines(self) -> None:
        print("Checking external AI engines...")
        try:
            import os
            import httpx

            checks = [
                ("Vane (vane_search)", os.environ.get("VANE_BASE_URL", "http://127.0.0.1:3000").rstrip("/"), "/api/providers"),
                ("AgenticSeek (agenticseek_task)", os.environ.get("AGENTICSEEK_BASE_URL", "http://127.0.0.1:7777").rstrip("/"), "/health"),
            ]
            for label, base, path in checks:
                try:
                    with httpx.Client(timeout=3.0) as client:
                        resp = client.get(f"{base}{path}")
                        if resp.status_code < 400:
                            print(f"  [ONLINE]  {label}  {base}")
                        else:
                            print(f"  [ERROR]   {label}  {base} (HTTP {resp.status_code})")
                except Exception:
                    print(f"  [OFFLINE] {label}  {base}")
        except Exception as exc:
            print(f"  Could not check engine status: {exc}")
        print()
        print(ENGINES)

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
    parser.add_argument("--headless", action="store_true", help="Run without REPL (background/autostart mode)")
    parser.add_argument("--port", type=int, default=8080, help="Web dashboard port (default: 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="Web dashboard host (default: 127.0.0.1)")
    parser.add_argument("--lan", action="store_true", help="Bind to 0.0.0.0 for LAN/mobile access (e.g. from Android)")
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

    if args.lan:
        args.host = "0.0.0.0"

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

    # Duplicate instance prevention: create a platform-specific lock.
    # Windows: named mutex; POSIX: file lock.
    _jarvis_mutex = None
    _lock_file = None
    try:
        if sys.platform == "win32":
            mutex_name = "JarvisMutex_{}".format("ultron".encode().hex())
            # use_last_error=True is required for ctypes.get_last_error() to
            # capture the CreateMutexW WIN32 error (ERROR_ALREADY_EXISTS=183).
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            mutex = kernel32.CreateMutexW(None, True, mutex_name)
            last_error = ctypes.get_last_error()
            if last_error == 183:  # ERROR_ALREADY_EXISTS
                logger.error("Another JARVIS instance is already running (mutex: %s)", mutex_name)
                print("Another JARVIS instance is already running. Only one instance may run at a time.")
                return 1
            _jarvis_mutex = mutex
        else:
            # POSIX: use a lock file
            import fcntl
            lock_path = Path.home() / ".ultron" / ".lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            _lock_file = open(lock_path, "w")
            try:
                fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                print("Another JARVIS instance is already running. Only one instance may run at a time.")
                return 1
    except Exception:
        logger.warning("Could not create lock for instance prevention")

    # Ensure lock is cleaned up on exit
    def cleanup_mutex() -> None:
        if _jarvis_mutex is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(_jarvis_mutex)
            except Exception:
                pass
        if _lock_file is not None:
            try:
                import fcntl
                fcntl.flock(_lock_file, fcntl.LOCK_UN)
                _lock_file.close()
            except Exception:
                pass

    import atexit
    atexit.register(cleanup_mutex)

    # ... rest of main() continues

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

    from ultron.memory.semantic import SemanticMemory
    from ultron.services import get_memory_service
    if str(config.memory_file):
        memory: Memory = SemanticMemory(config.memory_file)
    else:
        memory = Memory()
    get_memory_service().set_engine(memory if isinstance(memory, SemanticMemory) else None)

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

        if args.lan:
            import socket as _socket
            lan_ips = []
            try:
                for info in _socket.getaddrinfo(_socket.gethostname(), None, _socket.AF_INET):
                    ip = info[4][0]
                    if not ip.startswith("127."):
                        lan_ips.append(ip)
            except Exception:
                pass
            # Fallback: connect to a public IP to discover local interface
            if not lan_ips:
                try:
                    with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as s:
                        s.connect(("8.8.8.8", 80))
                        lan_ips.append(s.getsockname()[0])
                except Exception:
                    pass
            if lan_ips:
                print(f"\n  LAN access (Android / other devices on same WiFi):")
                for ip in set(lan_ips):
                    print(f"    http://{ip}:{args.port}")
                print(f"\n  Open this URL in your Android browser to use ULTRON.")
            else:
                print(f"\n  LAN mode enabled but could not detect local IP.")
                print(f"  Check your WiFi IP manually and use: http://<your-ip>:{args.port}")

        # Wait for server to be ready before opening UI
        print("Waiting for JARVIS server to be ready...")
        ready = False
        for i in range(30):  # wait up to 30 seconds
            try:
                import httpx

                resp = httpx.get(f"http://{args.host}:{args.port}/api/status", timeout=2)
                if resp.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            _time.sleep(1.0)
        if ready:
            print("JARVIS server is ready.")
        else:
            print("Warning: JARVIS server did not respond within 30 seconds. Proceeding anyway.")

        # Get screen resolution for kiosk mode (Windows only)
        try:
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            print(f"Screen resolution: {screen_width}x{screen_height}")
        except (ImportError, Exception):
            screen_width, screen_height = 1920, 1080  # fallback

        def _open_browser():
            _time.sleep(0.5)
            try:
                webbrowser.open(url)
            except Exception:
                webbrowser.open(url)
        import threading
        threading.Thread(target=_open_browser, daemon=True).start()

    cli = Cli(agent=agent, memory=memory, registry=registry, brain=brain)
    if args.headless:
        # Autostart/background mode: keep the web server alive, no REPL.
        # This prevents input() from getting EOF (no console) and shutdown.
        logger.info("Ultron running in headless mode [dashboard=%s]",
                    f"http://{args.host}:{args.port}" if args.web else "disabled")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            if web_server:
                web_server.shutdown()
        return 0

    try:
        return cli.repl()
    finally:
        logger.info("Ultron shutdown [turns=%d]", len(memory))
        if web_server:
            web_server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
