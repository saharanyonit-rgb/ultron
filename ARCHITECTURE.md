# ARCHITECTURE.md - JARVIS Desktop Application

## Overview

JARVIS is a Windows desktop application that wraps the existing ULTRON AI assistant
in a native desktop experience with system tray integration, auto-start backend,
and a polished web-based UI.

## System Architecture

```
JARVIS Desktop Application
│
├── Desktop Shell (desktop/)
│   ├── main.py           # Entry point, lifecycle management
│   ├── process.py        # Backend process management
│   ├── tray.py           # System tray integration (pystray)
│   ├── config.py         # Desktop configuration (%APPDATA%/JARVIS/)
│   ├── notifications.py  # Windows notifications
│   ├── startup.py        # Windows startup registration
│   └── __main__.py       # python -m desktop entry
│
├── ULTRON Backend (ultron/)
│   ├── cli.py            # CLI entry point
│   ├── web.py            # HTTP API server (http.server)
│   ├── web_api.py        # System metrics, agent status
│   ├── web_broadcaster.py # SSE event fan-out
│   ├── web_static.py     # Static file serving
│   ├── config.py         # Configuration (.env loading)
│   ├── core/             # Brain, Agent, Router
│   ├── llm/              # 11 LLM providers
│   ├── tools/            # 60+ tools
│   ├── memory/           # 3-tier memory system
│   ├── brains/           # Multi-model brain orchestration
│   ├── orchestrator.py   # Phase 5 autonomous orchestrator
│   ├── agents/           # Specialized agents
│   ├── services/         # Calendar, Notes, Reminders
│   └── actions/          # Permissions, audit logging
│
├── Frontend (frontend/)
│   ├── index.html        # Single-page application
│   ├── js/app.js         # Application logic (1277 lines)
│   ├── js/api.js         # REST + SSE API layer (348 lines)
│   └── css/main.css      # Dark theme design system (1095 lines)
│
└── Build System
    ├── jarvis.spec        # PyInstaller onedir configuration
    ├── jarvis_onefile.spec# PyInstaller single-file configuration
    ├── build.bat          # Windows batch build script
    ├── build.ps1          # PowerShell build script
    ├── package.bat        # Release packaging script (batch)
    ├── package.ps1        # Release packaging script (PowerShell)
    ├── installer/         # Inno Setup installer (JARVIS.iss)
    └── generate_icon.py   # Icon generation
```

## Process Architecture

```
JARVIS.exe (PyInstaller bundle)
    │
    ├── desktop/main.py
    │   ├── InProcessBackend (desktop/server.py)
    │   │   ├── Runs JarvisAPI in a daemon thread (no subprocess)
    │   │   ├── Health check loop (HTTP polling)
    │   │   ├── Crash detection & auto-restart
    │   │   └── Port conflict resolution
    │   │
    │   ├── SystemTray (pystray)
    │   │   ├── Open JARVIS
    │   │   ├── Show/Hide
    │   │   └── Exit
    │   │
    │   ├── NotificationManager
    │   │   └── Windows toast notifications
    │   │
    │   └── Single Instance (named mutex)
    │
    └── Browser UI
        └── http://127.0.0.1:8080
```

> Note: The earlier subprocess design (`desktop/process.py`, `ultron_backend.py`)
> is superseded by the in-process backend. `desktop/server.py` wires the same
> components as `ultron/cli.py` (config → provider → registry → agent → brain →
> JarvisAPI) but runs them in-process so the whole app is a single process with
> no external executable dependency. `desktop/process.py` is retained as legacy
> reference code and is not used by `desktop/main.py`.

## Communication Flow

```
User Action (Browser UI)
    │
    ├── REST API (HTTP POST/GET)
    │   └── http://127.0.0.1:8080/api/*
    │
    └── SSE Events (EventSource)
        └── http://127.0.0.1:8080/api/events
            │
            ▼
ULTRON Backend (http.server)
    │
    ├── JarvisRequestHandler
    │   ├── API routes (30+ endpoints)
    │   ├── Static file serving
    │   └── SSE streaming
    │
    ├── Brain / Orchestrator
    │   ├── Intent routing
    │   ├── Goal decomposition
    │   ├── Task execution
    │   └── Verification
    │
    ├── LLM Providers
    │   ├── 11 providers
    │   └── Automatic failover
    │
    └── Tool Execution
        ├── 60+ tools
        ├── Permission checks
        ├── Risk classification
        └── Audit logging
```

## Configuration

### Desktop Configuration

Stored in `%APPDATA%/JARVIS/desktop_config.json`:
- Window size/position
- Backend port
- Close-to-tray behavior
- Start with Windows
- Notification preferences
- Theme/accent color

### Backend Configuration

Stored in `.env` (project root) or `%APPDATA%/JARVIS/.env`:
- AI provider selection
- API keys
- Model configuration
- Memory settings
- Security settings
- Tool configuration

### Data Storage

- `%APPDATA%/JARVIS/logs/` - Application logs
- `%APPDATA%/JARVIS/desktop_config.json` - Desktop settings
- `~/.ultron/memory.jsonl` - Conversation memory
- `~/.jarvis/calendar.json` - Calendar events
- `~/.jarvis/notes.json` - Notes
- `~/.jarvis/reminders.json` - Reminders
- `~/.ultron/audit.log` - Security audit log

## Security

### Credential Handling

- API keys stored in `.env` (never hardcoded)
- Desktop config does not store secrets
- `.env` is git-ignored
- Logs redact secrets automatically

### Network Security

- Backend binds to `127.0.0.1` only (no external access)
- CORS headers prevent cross-origin requests
- Browser security guards validate navigation
- Network security guards block private IPs

### Tool Security

- Permission gates for mutating operations
- Risk classification (READ/LOW/MEDIUM/HIGH/CRITICAL)
- Policy engine with configurable rules
- Blocked command patterns
- Filesystem path validation
- Audit logging for all operations

## Performance

- Backend starts in < 3 seconds
- Health check every 3 seconds
- Crash recovery with 3 auto-restarts
- SSE for real-time updates (no polling for critical events)
- Smart polling with change detection (2-30 second intervals)
- Static file caching with ETags
- Gzip compression for large responses

## Build Pipeline

```
validate environment
    ↓
install/check dependencies
    ↓
run tests (optional)
    ↓
generate icon (optional)
    ↓
PyInstaller analysis
    ↓
bundle Python runtime
    ↓
bundle ULTRON package
    ↓
bundle frontend files
    ↓
create JARVIS.exe
    ↓
verify output
    ↓
create release directory
```

## Extension Points

### Adding a New Tool

1. Create `ultron/tools/new_tool.py`
2. Subclass `Tool`, implement `name`, `description`, `parameters`, `run()`
3. Register in `ultron/tools/__init__.py`
4. Add keyword mappings in `ultron/core/router.py`
5. Add to `hiddenimports` in `jarvis.spec`

### Adding a New LLM Provider

1. Create `ultron/llm/new_provider.py`
2. Subclass `LLMProvider`, implement `complete()`, `feed_tool_results()`
3. Add branch in `ultron/llm/__init__.py:build_provider()`
4. Add to `SUPPORTED_PROVIDERS` in `config.py`
5. Add to `hiddenimports` in `jarvis.spec`

### Adding a New Brain

1. Create `ultron/brains/new_brain.py`
2. Subclass appropriate brain base
3. Register in `ultron/brains/__init__.py`
4. Add config in `BrainConfig`
5. Add to `hiddenimports` in `jarvis.spec`
