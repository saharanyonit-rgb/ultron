<div align="center">
# ⚡ ULTRON - JARVIS-Style Personal AI Desktop Assistant
[![CI](https://github.com/saharanyonit-rgb/ultron/actions/workflows/ci.yml/badge.svg)](https://github.com/saharanyonit-rgb/ultron/actions/workflows/ci.yml)
[![CodeQL](https://github.com/saharanyonit-rgb/ultron/actions/workflows/codeql.yml/badge.svg)](https://github.com/saharanyonit-rgb/ultron/actions/workflows/codeql.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1000%20passing-brightgreen.svg)](tests/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)
**11 LLM providers · 60+ tools · 6 specialized brains · 3-tier memory · Desktop + Android**
[Download Latest Release](https://github.com/saharanyonit-rgb/ultron/releases/latest) · [Architecture](ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)
</div>
---
## What is Ultron?
Ultron is a modular, **JARVIS-style AI desktop assistant** for Windows. Talk to it in plain text (or by voice), and it plans, routes, and executes - using the right tool, the right model, and the right brain for each task.
```
You → "Research quantum error correction, write a report, and email it to me"
       ↓
  Research Brain → Planning Brain → Coding Brain → Verification Brain
       ↓                ↓                ↓
   Web search     Task graph       Format report    → Email sent ✓
```
**It runs entirely on your machine.** The server binds to `127.0.0.1` by default. No telemetry. No cloud sync. Your data stays local.
---
## Features at a Glance
| Layer | What's there |
|---|---|
| **LLM Providers** | Google Gemini, OpenAI, Anthropic, NVIDIA, OpenRouter, Grok, Azure, Cohere, Mistral, Perplexity, AWS Bedrock |
| **Specialized Brains** | Planning, Research, Coding, Computer-Vision, Verification, Fast |
| **Tools** | 60+ - files, browser, clipboard, calendar, screenshots, voice, web APIs, system, database, and more |
| **Memory** | 3-tier: in-session → persistent (JSONL) → semantic (vector) |
| **Orchestration** | Simple, Phase-5 autonomous (TaskGraph), and Phase-7 multi-brain |
| **Interfaces** | CLI, Web UI (SSE streaming), Windows Desktop (pystray), Android companion |
| **Security** | Permission gates, risk classification, audit log, secret redaction, sandboxing |
| **Tests** | 1001 tests · 1000 passing · 27 real_e2e excluded by default |
---
## Quick Start
### Option A - Download the Windows Executable
1. Grab **JARVIS.exe** from [Releases](https://github.com/saharanyonit-rgb/ultron/releases/latest)
2. Copy `.env.example` → `.env` and add at least one API key
3. Run `JARVIS.exe`
### Option B - Run from Source
```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
cd ultron
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
# Edit .env - set ULTRON_PROVIDER and the matching API key
```
**Terminal mode:**
```powershell
python -m ultron
```
**Web UI (http://127.0.0.1:8080):**
```powershell
python -m ultron --web
```
**Desktop shell (system tray):**
```powershell
python -m desktop
```
---
## Configuration
Copy `.env.example` to `.env` and set your provider:
```env
ULTRON_PROVIDER=openrouter
ULTRON_OPENROUTER_API_KEY=your_key_here
ASSISTANT_NAME=JARVIS
WAKE_WORD=hi jarvis
LOG_LEVEL=INFO
```
### Supported Providers
| Provider | Env var | Free tier |
|---|---|---|
| **OpenRouter** | `ULTRON_OPENROUTER_API_KEY` | ✅ Free models available |
| **Google Gemini** | `GEMINI_API_KEY` | ✅ Free tier |
| **NVIDIA** | `ULTRON_NVIDIA_API_KEY` | ✅ Free tier |
| **OpenAI** | `OPENAI_API_KEY` | - |
| **Anthropic** | `ANTHROPIC_API_KEY` | - |
| **xAI (Grok)** | `ULTRON_GROK_API_KEY` | - |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` | - |
| **Cohere** | `COHERE_API_KEY` | - |
| **Mistral** | `MISTRAL_API_KEY` | - |
| **Perplexity** | `PERPLEXITY_API_KEY` | - |
| **AWS Bedrock** | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | - |
---
## Project Structure
```
ultron/               # Core Python package
  core/               # Brain, Agent, Router
  llm/                # One file per LLM provider (11 providers)
  brains/             # Specialized brain orchestration (Phase 7)
  tools/              # 60+ tool implementations
  memory/             # In-session, persistent, semantic
  actions/            # Permission gates, audit logging
  orchestrator.py     # Phase-5 autonomous TaskGraph orchestrator
  web.py              # HTTP + SSE API server
  cli.py              # Terminal REPL entry point
  config.py           # Typed config + .env parser
frontend/             # Vanilla HTML/CSS/JS web UI (zero deps)
desktop/              # Windows desktop shell (pystray)
android/              # Android companion app source
tests/                # 1001-test pytest suite
scripts/              # Dev utilities and launcher helpers
docs/                 # Architecture docs and audit reports
```
---
## Running Tests
```powershell
python -m pytest tests/ -v
python -m pytest tests/ --cov=ultron --cov-report=term-missing
python -m pytest tests/ -v -m real_e2e
```
---
## Architecture
See [ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown.
| Path | When | How |
|---|---|---|
| Simple | Quick questions | Brain → Agent → LLM + tools |
| Phase 5 | Autonomous goals | Orchestrator → TaskGraph → parallel |
| Phase 7 | Complex, multi-domain | BrainOrchestrator → 6 specialized brains |
---
## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md).
---
## Security
See [SECURITY.md](SECURITY.md). The server is `127.0.0.1`-only by default.
---
## License
[MIT](LICENSE) - © saharanyonit-rgb
