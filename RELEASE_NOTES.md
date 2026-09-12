# RELEASE_NOTES.md - JARVIS Desktop Application

## v0.1.0 - Initial Desktop Release

### What's New

- **Desktop Application:** JARVIS is now available as a standalone Windows desktop application
- **System Tray Integration:** JARVIS runs in the system tray with Open/Show/Hide/Exit controls
- **Auto-Start Backend:** The ULTRON backend starts automatically when JARVIS launches
- **Health Monitoring:** Continuous health checks with automatic crash recovery
- **Port Conflict Resolution:** Automatic port selection if the default port is in use
- **Single Instance:** Only one JARVIS instance runs at a time (named mutex)
- **Windows Notifications:** Native toast notifications for status updates
- **Close to Tray:** JARVIS minimizes to the system tray instead of closing
- **Start with Windows:** Optional registration for Windows startup (user-controlled)
- **Settings Persistence:** Desktop settings saved in `%APPDATA%/JARVIS/`
- **Structured Logging:** Application logs stored in `%APPDATA%/JARVIS/logs/`

### Existing Features (Preserved)

- **11 AI Providers:** Gemini, NVIDIA, OpenRouter, Grok, OpenAI, Azure, Anthropic, Cohere, Mistral, Perplexity, Bedrock
- **60+ Tools:** Filesystem, apps, browser, system, voice, calendar, notes, reminders, memory, database, git, GitHub, web API, UI
- **3-Tier Memory:** In-memory, persistent JSONL, semantic search with keyword indexing
- **Multi-Model Brains:** 6 specialized brains with dedicated models (planning, research, coding, computer, verification, fast)
- **Phase 5 Orchestrator:** Goal engine, task graph, parallel execution, verification, recovery
- **Permission System:** Multi-layer permissions with risk classification and policy engine
- **Voice Integration:** Text-to-speech (pyttsx3) and speech-to-text (SpeechRecognition)
- **Web UI:** Desktop-style dark theme with real-time SSE updates
- **918+ Tests:** Comprehensive test suite with 1000/1001 passing

### Architecture

- **Desktop Shell:** Python with pystray for system tray integration
- **Backend:** Pure Python HTTP server (http.server + ThreadingMixin)
- **Frontend:** Vanilla HTML/CSS/JavaScript (zero dependencies)
- **Packaging:** PyInstaller for standalone executable (one-file + onedir portable)
- **Configuration:** .env file + %APPDATA%/JARVIS/desktop_config.json

### Release Artifacts

- **`JARVIS.exe`** - Standalone single-file executable (68.5 MB, self-contained)
- **`JARVIS-Portable.zip`** - Portable onedir package (68.4 MB, fastest startup, unzip-and-run)

### Known Limitations

- **Browser Required:** The UI opens in the default web browser (not a native window)
- **No React/TypeScript Frontend:** The existing vanilla JS frontend is preserved as-is
- **No Installer:** Currently produces a standalone executable and portable zip, not an MSI/NNSIS installer (installer script `installer/JARVIS.iss` for Inno Setup included)
- **Voice Hardware:** Requires microphone and speakers for voice features
- **Playwright Optional:** Browser automation requires Playwright installation
- **Crash Recovery:** A forced kill (`taskkill /F`) of the one-file executable can leave the child process running; use the tray Exit control for normal shutdown

### Bug Fixes

- Fixed `web_static.py` frontend path resolution for PyInstaller bundled mode
- Fixed `config.py` .env file search to support bundled mode (multiple search locations)
- Fixed standalone `JARVIS.exe` packaging: onedir exe requires `_internal` folder, so the standalone artifact is now a true single-file build (`jarvis_onefile.spec`)

### Security

- No API keys hardcoded in source
- Backend binds to localhost only
- Secrets redacted from logs
- Permission system for dangerous operations
- Audit logging for all tool executions

### Testing

```
Baseline:  1000 passed, 1 failed, 27 deselected
Final:     1000 passed, 1 failed, 27 deselected
Regressions: 0
```

### Files Created

- `desktop/` - Desktop application shell (8 files)
- `jarvis.spec` - PyInstaller onedir build configuration
- `jarvis_onefile.spec` - PyInstaller single-file build configuration
- `ultron_desktop_entry.py` - One-file entry point
- `build.bat` - Windows batch build script
- `build.ps1` - PowerShell build script
- `package.bat` / `package.ps1` - Release packaging scripts
- `installer/JARVIS.iss` - Inno Setup installer script
- `LICENSE` - MIT License
- `generate_icon.py` - Icon generation script
- `ultron_backend.py` - Backend entry point for bundling
- `ARCHITECTURE.md` - Architecture documentation
- `BUILD.md` - Build instructions
- `RELEASE_NOTES.md` - This file
- `docs/ARCHITECTURE_AUDIT.md` - Full project audit

### Files Modified

- `ultron/web_static.py` - Bundled mode frontend path resolution
- `ultron/config.py` - Bundled mode .env file search
- `pyproject.toml` - Added desktop dependencies and entry points
- `.gitignore` - Added release directory
- `README.md` - Resolved merge conflict, updated documentation

### Upgrade Notes

This release is backward-compatible. The existing ULTRON system continues to work exactly as before. The desktop application is an additional entry point that wraps the existing system.
