 # ULTRON

### JARVIS-Style Personal AI Desktop Assistant for Windows

Ultron is a modular, terminal-callable AI desktop assistant designed for Windows. It combines LLM reasoning, structured task planning, tool execution, verification, memory, permissions, and multi-provider AI routing into one assistant architecture.

> **Current Version:** Phase 5 Build
> **Platform:** Windows
> **Python:** 3.12+

---

# Table of Contents

* [What is Ultron?](#what-is-ultron)
* [Features](#features)
* [Architecture](#architecture)
* [Requirements](#requirements)
* [Installation](#installation)
* [Clone the Repository](#clone-the-repository)
* [Create the Python Environment](#create-the-python-environment)
* [Install Dependencies](#install-dependencies)
* [Configure API Keys](#configure-api-keys)
* [`.env.example` vs `.env`](#envexample-vs-env)
* [Start Ultron](#start-ultron)
* [REPL Commands](#repl-commands)
* [Running Tests](#running-tests)
* [Project Structure](#project-structure)
* [Troubleshooting](#troubleshooting)
* [Security](#security)
* [Development](#development)
* [License](#license)

---

# What is Ultron?

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

# Features

## AI and Reasoning

* LLM provider abstraction
* Multi-provider routing
* Intelligent request routing
* Goal understanding
* Multi-step planning
* Task orchestration
* Response generation
* Semantic verification

## Agent System

Ultron contains specialized agents for different types of work, including:

* Coding
* Research
* Vision
* General task execution
* LLM-based agent operations

## Memory

Ultron provides:

* Persistent memory
* Semantic memory
* Memory management
* Context management
* Conversation history

## Tool System

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

## Security and Control

Ultron includes mechanisms for:

* Permission management
* Risk evaluation
* Execution control
* Sandboxing
* Audit logging
* Network security enforcement
* Semantic verification

---

# Architecture

The high-level architecture can be viewed as:

```text
User Input
    │
    ▼
Router
    │
    ▼
Brain / Intelligence Layer
    │
    ▼
Goal Understanding
    │
    ▼
Planner
    │
    ▼
Agent / Tool Selection
    │
    ▼
Permission & Risk Control
    │
    ▼
Tool Execution
    │
    ▼
Verification
    │
    ▼
Memory / Context Update
    │
    ▼
Response
```

The architecture is divided into several major components:

```text
ultron/
├── agents/
├── brains/
├── core/
├── llm/
├── memory/
├── services/
├── tools/
└── windows/
```

---

# Requirements

Before installing Ultron, make sure you have the following.

## Operating System

* Windows

## Python

Ultron requires:

```text
Python >= 3.12
```

Check your installed Python version:

```powershell
python --version
```

or:

```powershell
py --version
```

## Git

Git is required to clone and update the repository.

Check Git:

```powershell
git --version
```

## Internet Connection

A network connection is required when using cloud-based AI providers or other network-dependent functionality.

---

# Installation

## 1. Clone the Repository

Clone the official repository:

```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
```

Enter the project directory:

```powershell
cd ultron
```

---

# Create the Python Environment

Create a Python 3.12 virtual environment:

```powershell
py -3.12 -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

After activation, your PowerShell prompt should show something similar to:

```text
(.venv) PS D:\ultron>
```

Verify Python:

```powershell
python --version
```

---

# Install Dependencies

Install Ultron and its development dependencies:

```powershell
pip install -e ".[dev]"
```

This installs the project in editable mode and includes the development dependencies required for testing and development.

If you need to update the package installer first:

```powershell
python -m pip install --upgrade pip
```

Then:

```powershell
pip install -e ".[dev]"
```

---

# Configure API Keys

Ultron supports configurable AI providers.

API credentials should be stored in environment variables rather than being hardcoded into source code.

## Create `.env`

Ultron provides a `.env.example` file as a **safe configuration template**.

Create your local `.env` file:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your preferred editor.

For example:

```env
GEMINI_API_KEY=your_api_key_here
ULTRON_PROVIDER=gemini
```

Use your own API credentials.

---

# `.env.example` vs `.env`

This distinction is important.

| File           | Commit to GitHub? | Purpose                                            |
| -------------- | ----------------- | -------------------------------------------------- |
| `.env.example` | Yes               | Safe configuration template                        |
| `.env`         | No                | Local configuration containing private credentials |

### `.env.example`

`.env.example` is intentionally included in the repository.

It tells users which environment variables Ultron expects without exposing real credentials.

Example:

```env
GEMINI_API_KEY=
ULTRON_PROVIDER=gemini
```

### `.env`

`.env` is created locally on each user's computer.

It may contain real API keys:

```env
GEMINI_API_KEY=your_real_key
ULTRON_PROVIDER=gemini
```

**Never commit this file.**

---

# API Key Security

Follow these rules when configuring Ultron:

### Never:

* Commit `.env`
* Put real API keys inside Python files
* Put API keys inside frontend JavaScript
* Put API keys inside README files
* Share API keys publicly
* Commit private credentials

### Do:

* Use `.env` for local credentials
* Use `.env.example` as the public template
* Use system environment variables when appropriate
* Rotate credentials immediately if they are accidentally exposed

Ultron loads credentials from environment configuration.

Real environment variables take precedence over `.env` values.

---

# Start Ultron

After installing dependencies and configuring your environment, start Ultron with:

```powershell
.\.venv\Scripts\python -m ultron
```

Ultron will start its terminal interface.

You can then enter requests such as:

```text
ultron> what's my CPU and free disk space?
```

Ultron can select the appropriate system-information capability and return the result.

Another example:

```text
ultron> create a file with "buy milk"
```

For permission-controlled actions, Ultron may ask:

```text
[permission] Allow 'create_file'? [y/N]:
```

After confirmation:

```text
[ran] create_file {...}
```

---

# REPL Commands

Ultron provides several built-in REPL commands.

```text
/help
/tools
/history
/clear
/permissions
/memory
/exit
```

## `/help`

Displays available REPL commands and information.

## `/tools`

Displays available tools.

## `/history`

Displays conversation history.

## `/clear`

Clears the current conversation context.

## `/permissions`

Displays or manages permission-related information.

## `/memory`

Displays memory-related information.

## `/exit`

Exits Ultron.

---

# Running Tests

Ultron includes an extensive automated test suite.

Run the tests with:

```powershell
.\.venv\Scripts\python -m pytest
```

Or, if the virtual environment is activated:

```powershell
pytest
```

The test suite covers areas such as:

* Agents
* Brains
* Configuration
* Memory
* Planning
* Routing
* Permissions
* Tools
* Pipeline execution
* Verification
* Web APIs
* Phase-specific functionality
* Integration behavior

Tests use mocked or fake providers where appropriate.

Real end-to-end tests are marked separately and are excluded from the normal test run.

---

# Project Structure

```text
ultron/
│
├── actions/
│   ├── audit_log.py
│   └── permissions.py
│
├── agents/
│   ├── coding.py
│   ├── llm_agent.py
│   ├── research.py
│   ├── task.py
│   └── vision.py
│
├── brains/
│   ├── capability_router.py
│   ├── coding.py
│   ├── computer.py
│   ├── orchestrator.py
│   ├── planning.py
│   ├── provider.py
│   ├── research.py
│   ├── router.py
│   └── verification.py
│
├── core/
│   ├── agent.py
│   ├── brain.py
│   └── router.py
│
├── llm/
│   ├── anthropic.py
│   ├── azure_openai.py
│   ├── bedrock.py
│   ├── cohere.py
│   ├── gemini.py
│   ├── grok.py
│   ├── mistral.py
│   ├── nvidia.py
│   ├── openai.py
│   ├── openrouter.py
│   ├── perplexity.py
│   └── router.py
│
├── memory/
│   ├── persistent.py
│   └── semantic.py
│
├── services/
│   ├── calendar.py
│   ├── notes.py
│   └── reminders.py
│
├── tools/
│   ├── apps.py
│   ├── automation.py
│   ├── browser_tools.py
│   ├── calendar_tool.py
│   ├── clipboard.py
│   ├── command.py
│   ├── database.py
│   ├── execute.py
│   ├── execution.py
│   ├── file_ops.py
│   ├── filesystem.py
│   ├── screenshot.py
│   ├── sysinfo.py
│   ├── urls.py
│   ├── vision.py
│   └── voice.py
│
├── windows/
│
├── cli.py
├── config.py
├── credentials.py
├── goal.py
├── llm_goal.py
├── llm_planner.py
├── memory_manager.py
├── models.py
├── orchestrator.py
├── pipeline.py
├── planner.py
├── policy.py
├── recovery.py
├── response.py
├── risk.py
├── sandbox.py
├── status.py
├── task.py
├── tool_selection.py
├── verification.py
└── web.py
```

Additional repository directories:

```text
frontend/
tests/
```

The `frontend/` directory contains the web interface.

The `tests/` directory contains the automated test suite.

---

# Troubleshooting

## `ModuleNotFoundError`

Make sure the virtual environment is activated:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then reinstall the project:

```powershell
pip install -e ".[dev]"
```

---

## Python Is Not Recognized

Check whether Python is installed:

```powershell
py --version
```

Ultron requires Python 3.12 or newer.

If Python 3.12 is installed:

```powershell
py -3.12 --version
```

---

## Virtual Environment Will Not Activate

If PowerShell blocks activation, you can allow the execution policy for the current PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## API Key Errors

Check that `.env` exists:

```powershell
Test-Path .env
```

It should return:

```text
True
```

Check that the required provider is configured.

For example:

```env
ULTRON_PROVIDER=gemini
```

Make sure the corresponding API credential is available.

**Do not post your API key when asking for help.**

---

## `ULTRON_PROVIDER` Is Not Set

Configure a supported provider in `.env`.

Example:

```env
ULTRON_PROVIDER=gemini
```

Make sure the corresponding API credentials are also configured.

---

## Permission Prompts

Ultron may request confirmation before executing protected tools.

For example:

```text
[permission] Allow 'create_file'? [y/N]:
```

Review the requested action before confirming it.

Permission behavior is controlled by Ultron's permission and policy systems.

---

## Tests Report a Provider Problem

If tests report that no provider is configured, verify:

```text
ULTRON_PROVIDER
```

and the corresponding provider configuration.

For normal tests, mocked/fake providers should be used where supported.

---

## Dependencies Are Missing

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then reinstall:

```powershell
pip install -e ".[dev]"
```

---

# Security

Ultron is a desktop assistant with access to tools that can interact with the operating system.

Because of this, security should be treated as an important part of deployment and development.

Ultron includes components for:

* Permission management
* Risk evaluation
* Execution control
* Audit logging
* Sandboxing
* Network security
* Verification

### Before Running Ultron

Review:

* Enabled tools
* Provider configuration
* Permission settings
* Environment variables
* Network configuration

Never run unknown code or configuration without reviewing it first.

---

# Development

To work on Ultron:

```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
cd ultron
```

Create the development environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install development dependencies:

```powershell
pip install -e ".[dev]"
```

Run tests:

```powershell
pytest
```

Start Ultron:

```powershell
python -m ultron
```

---

# Git Workflow

After making changes:

```powershell
git status
```

Review your changes:

```powershell
git diff
```

Stage changes:

```powershell
git add .
```

Commit:

```powershell
git commit -m "Describe your changes"
```

Push:

```powershell
git push
```

Before committing, make sure private files such as `.env` are not staged.

You can verify `.env` is ignored with:

```powershell
git check-ignore .env
```

Expected output:

```text
.env
```

---

# Important Files

| File                   | Purpose                                              |
| ---------------------- | ---------------------------------------------------- |
| `.env.example`         | Public configuration template                        |
| `.gitignore`           | Prevents private/unwanted files from being committed |
| `README.md`            | Project documentation                                |
| `pyproject.toml`       | Python project configuration                         |
| `requirements.txt`     | Runtime dependencies                                 |
| `requirements-dev.txt` | Development dependencies                             |
| `uv.lock`              | Dependency lock file                                 |
| `tests/`               | Automated tests                                      |
| `frontend/`            | Web interface                                        |
| `ultron/`              | Main application source                              |

---

# License

A license has not been specified in this guide.

Choose and add an appropriate open-source license before presenting the project as open source.

---

# Project Status

**Ultron — Phase 5 Build**

The project is under active development.

The architecture is designed to evolve through additional phases, features, agents, tools, providers, memory capabilities, and reliability improvements.
