# ULTRON

### JARVIS-Style Personal AI Desktop Assistant for Windows

Ultron is a modular, terminal-callable AI desktop assistant designed for Windows. It combines LLM reasoning, structured task planning, tool execution, verification, memory, permissions, and multi-provider AI routing into one assistant architecture.

> **Current Version:** Phase 5 Build (Phase 7 Brains)
> **Platform:** Windows
> **Python:** 3.12+

---

## Table of Contents

* [What is Ultron?](#what-is-ultron)
* [Features](#features)
* [Architecture](#architecture)
* [Requirements](#requirements)
* [Installation](#installation)
* [Configuration](#configuration)
* [Running](#running)
* [Tests](#tests)
* [Project Structure](#project-structure)
* [Desktop Application](#desktop-application)
* [Troubleshooting](#troubleshooting)
* [Security](#security)
* [Development](#development)
* [License](#license)

---

## What is Ultron?

Ultron is a **JARVIS-style personal AI desktop assistant for Windows**.

It is designed as a terminal-callable, text-in/text-out AI system capable of:

* Understanding user requests
* Routing requests to appropriate capabilities
* Planning multi-step tasks
* Selecting and executing tools
* Asking for permission before protected actions
* Verifying execution results
* Maintaining persistent memory
* Using semantic memory
* Working with multiple AI providers
* Using specialized agents
* Recovering from certain execution failures
* Interacting with Windows and desktop functionality

The project is built as a modular Python application so that individual components can be developed, tested, and extended independently.

---

## Features

### AI and Reasoning

* LLM provider abstraction
* Multi-provider routing with automatic fallback
* Intelligent request routing
* Goal understanding
* Multi-step planning
* Task orchestration
* Response generation
* Semantic verification

### Agent System

Ultron contains specialized agents for different types of work, including:

* Coding
* Research
* Vision
* General task execution
* LLM-based agent operations

### Memory

Ultron provides:

* Persistent memory
* Semantic memory
* Memory management
* Context management
* Conversation history

### Tool System

The tool architecture supports different categories of desktop and system operations, including:

* Applications
* Browser operations
* Clipboard
* Calendar
* Commands
* Database operations
* File operations
* Filesystem operations
* Screenshots
* System information
* URLs
* Voice
* Web APIs

### Security and Control

Ultron includes mechanisms for:

* Permission management
* Risk evaluation
* Execution control
* Sandboxing
* Audit logging
* Network security enforcement
* Semantic verification

---

## Architecture

### High-Level Flow

```
User Input
    |
    v
Router
    |
    v
Brain / Intelligence Layer
    |
    v
Goal Understanding
    |
    v
Planner
    |
    v
Agent / Tool Selection
    |
    v
Permission & Risk Control
    |
    v
Tool Execution
    |
    v
Verification
    |
    v
Memory / Context Update
    |
    v
Response
```

### Orchestration Layers

1. **Simple Path:** Brain -> Agent -> LLM + tools (conversational/quick requests)
2. **Phase 5 Path:** Orchestrator -> Goal -> TaskGraph -> parallel execution (autonomous goals)
3. **Phase 7 Path:** BrainOrchestrator -> specialized brains with dedicated models (complex tasks)

### Supported AI Providers

| Provider | Models |
|----------|--------|
| Google Gemini | gemini-3.5-flash, gemini-2.5-flash |
| NVIDIA | nemotron-3-ultra, nemotron |
| OpenRouter | 200+ models including free tier |
| xAI (Grok) | grok-3, grok-3-mini |
| OpenAI | gpt-4o, gpt-4o-mini |
| Azure OpenAI | Configurable deployments |
| Anthropic | claude-sonnet-4, claude-3.5-sonnet |
| Cohere | command-a, command-r-plus |
| Mistral | mistral-large-latest |
| Perplexity | sonar, sonar-pro |
| AWS Bedrock | Configurable models |

---

## Requirements

### Operating System

* Windows

### Python

Ultron requires:

```
Python >= 3.12
```

### Git

Git is required to clone and update the repository.

### Internet Connection

A network connection is required when using cloud-based AI providers.

---

## Installation

### 1. Clone the Repository

```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
cd ultron
```

### 2. Create the Python Environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```powershell
pip install -e ".[dev]"
```

### 4. Configure API Keys

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your preferred API keys.

---

## Configuration

### Provider Selection

Set the provider in `.env`:

```env
ULTRON_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
```

### Environment Variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `ULTRON_PROVIDER` | `gemini` | Active AI provider |
| `GEMINI_API_KEY` | — | Gemini API key |
| `ULTRON_MODEL` | `gemini-3.5-flash` | Model name |
| `ULTRON_TEMPERATURE` | `0.3` | Generation temperature |
| `ULTRON_MEMORY_FILE` | `~/.ultron/memory.jsonl` | Memory storage |
| `ULTRON_REQUIRE_PERMISSION` | `false` | Require confirmation for tools |
| `ULTRON_DEBUG` | `false` | Debug logging |

See `.env.example` for the complete list of 80+ configuration options.

---

## Running

### Terminal Mode

```powershell
.\.venv\Scripts\python -m ultron
```

### Web Mode

```powershell
.\.venv\Scripts\python -m ultron --web
```

Then open http://127.0.0.1:8080 in your browser.

### Desktop Mode

```powershell
.\.venv\Scripts\python -m desktop
```

This starts the JARVIS desktop application with system tray integration.

---

## Tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

The test suite covers:

* Agents, Brains, Configuration
* Memory, Planning, Routing
* Permissions, Tools, Pipeline
* Verification, Web APIs
* Phase-specific functionality
* Integration behavior

Tests use mocked providers where appropriate. Real E2E tests are marked separately.

**Test count: 1001 (1000 passed)**

---

## Project Structure

```
ultron/
├── agents/         # Specialized agent architecture
├── brains/         # Multi-model brain orchestration (Phase 7)
├── core/           # Agent, Brain, Router
├── llm/            # 11 LLM provider implementations
├── memory/         # In-memory, persistent, semantic memory
├── services/       # Calendar, Notes, Reminders, Memory services
├── tools/          # 60+ tool implementations
├── windows/        # Windows-specific utilities
├── actions/        # Permission gates, audit logging
├── cli.py          # Terminal REPL
├── config.py       # Configuration loading
├── orchestrator.py # Phase 5 autonomous orchestrator
├── web.py          # HTTP API server
└── ...

frontend/           # Vanilla HTML/CSS/JS web interface
desktop/            # Desktop application shell
tests/              # Automated test suite
docs/               # Documentation
```

---

## Desktop Application

JARVIS is also available as a Windows desktop application.

### Building

```powershell
.\build.ps1
```

### Features

* System tray integration
* Auto-start backend
* Close to tray
* Native Windows notifications
* Single instance detection
* Clean shutdown

### Output

```
release/
├── JARVIS.exe          # Standalone executable
├── README.md
└── RELEASE_NOTES.md
```

---

## Troubleshooting

### ModuleNotFoundError

Make sure the virtual environment is activated:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### API Key Errors

Check that `.env` exists and contains valid API keys:

```powershell
Test-Path .env
```

### Permission Prompts

Ultron may request confirmation before executing protected tools:

```
[permission] Allow 'create_file'? [y/N]:
```

---

## Security

Ultron is a desktop assistant with access to tools that can interact with the operating system.

Security components include:

* Permission management
* Risk evaluation
* Execution control
* Audit logging
* Sandboxing
* Network security
* Verification

### Before Running

Review:

* Enabled tools
* Provider configuration
* Permission settings
* Environment variables

Never run unknown code or configuration without reviewing it first.

---

## Development

```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
cd ultron
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
python -m ultron
```

---

## Project Status

**Ultron — Phase 5 Build (Phase 7 Brains)**

The project is under active development.

The architecture is designed to evolve through additional phases, features, agents, tools, providers, memory capabilities, and reliability improvements.
