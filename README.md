<<<<<<< HEAD
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
=======
# Ultron

A JARVIS-style personal AI desktop assistant for Windows. This is the **Phase 5** build: a terminal-callable, text-in/text-out agent wired to model providers with a small, explicit V1 tool set, structured pipeline, verification layer, error hierarchy, persistent memory, permissioned execution, multi-provider routing, intelligent semantic memory, multi-step planning, specialized agent architecture, semantic verification, controlled filesystem tools, command execution, sandbox execution, browser abstraction, advanced permissions, execution state persistence, recovery/replanning, audit observability, streaming execution status, autonomous goal engine, dependency-aware task graphs, goal-to-plan decomposition, agent orchestration with structured communication, parallel task execution, verification engine, context management, and final response generation.

## Scope

| In scope (Phase 5) | Out of scope (later phases) |
| --- | --- |
| Autonomous goal-oriented execution | UI (any) |
| Goal Engine with complexity assessment | Mouse/keyboard control (V5) |
| Dependency-aware Task Graph | Local models / Ollama (no usable GPU) |
| Goal Planner (goal → task graph) | Voice interface |
| Agent Manager with capability matching | Autonomous self-modification |
| Structured agent communication protocol | |
| Parallel independent task execution | |
| Verification Engine (structural + custom checks) | |
| Context Management (goal/task/agent layers) | |
| Final Response Engine with outcome classification | |
| Recovery and replanning integration | |
| Execution state persistence across interruptions | |
| Human approval gates via risk/policy layer | |
| All Phase 1-4 capabilities preserved | |

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Configure

```powershell
Copy-Item .env.example .env
# edit .env: set GEMINI_API_KEY (https://aistudio.google.com/app/apikey)
```

Real environment variables override `.env` values. Nothing is hardcoded.

### Core Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ULTRON_PROVIDER` | `gemini` | `gemini` or `nvidia` |
| `GEMINI_API_KEY` | — | required for Gemini provider |
| `ULTRON_NVIDIA_API_KEY` | — | required for NVIDIA provider |
| `ULTRON_MODEL` | `gemini-3.5-flash` | model name for the active provider |
| `ULTRON_TEMPERATURE` | `0.3` | low = reliable operator behavior |
| `ULTRON_MAX_TOOL_ITERATIONS` | `8` | guard against runaway tool loops |
| `ULTRON_AUDIT_LOG` | `~/.ultron/audit.log` | append-only action log |
| `ULTRON_SYSTEM_PROMPT` | built-in persona | override Ultron's personality |

### Phase 2 Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ULTRON_MEMORY_FILE` | `~/.ultron/memory.jsonl` | persistent conversation history |
| `ULTRON_REQUIRE_PERMISSION` | `false` | require confirmation for mutating tools |
| `ULTRON_PROVIDER_FALLBACK` | `""` | comma-separated fallback providers |

### Phase 3 Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ULTRON_MEMORY_ENABLED` | `true` | enable semantic memory |
| `ULTRON_MEMORY_RETRIEVAL_LIMIT` | `10` | max records returned by search |
| `ULTRON_MEMORY_RELEVANCE_THRESHOLD` | `0.1` | minimum relevance score for search results |
| `ULTRON_MAX_PLAN_STEPS` | `20` | maximum steps in a multi-step plan |
| `ULTRON_MAX_RETRIES` | `3` | retry limit for failed plan steps |
| `ULTRON_SEMANTIC_VERIFICATION` | `true` | enable semantic verification |
| `ULTRON_AGENT_EXECUTION_LIMIT` | `8` | max iterations per specialized agent |

### Phase 4 Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ULTRON_ALLOWED_FILESYSTEM_ROOTS` | `""` | comma-separated allowed filesystem roots |
| `ULTRON_SANDBOX_DIRECTORY` | `""` | sandbox working directory |
| `ULTRON_COMMAND_TIMEOUT` | `30` | timeout in seconds for command execution |
| `ULTRON_MAX_EXECUTION_TIME` | `300` | maximum total execution time |
| `ULTRON_PERMISSION_POLICY` | `default` | permission policy profile |
| `ULTRON_BROWSER_ENABLED` | `true` | enable browser abstraction |
| `ULTRON_EXECUTION_STATE_ENABLED` | `true` | enable execution state persistence |
| `ULTRON_EXECUTION_STATE_FILE` | `""` | path to execution state file |
| `ULTRON_AUDIT_LOG_ENABLED` | `true` | enable audit event logging |
| `ULTRON_MAX_CONCURRENT_TASKS` | `5` | maximum concurrent task executions |

### Advanced Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `ULTRON_DEBUG` | `false` | enable debug-level logging |
| `ULTRON_API_BASE_URL` | `""` | custom API base URL for providers |
| `ULTRON_TOOL_TIMEOUT` | `60` | timeout in seconds for tool execution |

## Run
>>>>>>> b26fbe8 (Initial Ultron project - JARVIS-style desktop assistant v0.1.0)

```powershell
.\.venv\Scripts\python -m ultron
```

<<<<<<< HEAD
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
=======
```
ultron> what's my CPU and free disk space?
  [ran] get_system_info {}
...answer...
ultron> create a file C:\Users\me\notes\todo.txt with "buy milk"
  [permission] Allow 'create_file' ({'path': '...', 'content': 'buy milk'})? [y/N]: y
  [ran] create_file {'path': '...', 'content': 'buy milk', 'overwrite': False}
...confirmation...
```

REPL commands: `/help` `/tools` `/history` `/clear` `/permissions` `/memory` `/exit`.

## Tests
>>>>>>> b26fbe8 (Initial Ultron project - JARVIS-style desktop assistant v0.1.0)

```powershell
.\.venv\Scripts\python -m pytest
```

<<<<<<< HEAD
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
=======
All tests use mocked/faked providers (no network required) except clipboard and screenshot tests which exercise real Windows APIs.

**Test count: 918 (891 passed across Phase 1-5)**

## Architecture

```
ultron/
├── cli.py              # terminal REPL (temporary frontend)
├── config.py           # .env loading → typed Config (no hardcoded keys)
├── errors.py           # structured error hierarchy
├── models.py           # RuntimeContext, Plan, ExecutionResult, VerificationResult, MemoryRecord, MultiStepPlan
├── pipeline.py         # deterministic execution flow (route → plan → execute → verify)
├── planner.py          # Phase 3: multi-step planning with dependency management
├── risk.py             # Phase 4: risk classification system
├── policy.py           # Phase 4: advanced permission policy engine
├── sandbox.py          # Phase 4: sandbox execution abstraction
├── browser.py          # Phase 4: browser automation abstraction
├── execution_state.py  # Phase 4: execution state persistence
├── recovery.py         # Phase 4: recovery and replanning
├── audit.py            # Phase 4: structured audit event system
├── status.py           # Phase 4: streaming execution status
├── verification.py     # tool result verification + Phase 3 semantic verification
├── logging_setup.py    # structured logging with secret redaction
├── goal.py             # Phase 5: Goal Engine — structured user objectives
├── task.py             # Phase 5: Task Model + dependency-aware TaskGraph
├── planner_v5.py       # Phase 5: Goal → TaskGraph planner
├── agent_manager.py    # Phase 5: Agent selection, communication, availability
├── orchestrator.py     # Phase 5: Central execution orchestrator
├── verification_v5.py  # Phase 5: Structured verification engine
├── context.py          # Phase 5: Layered context management
├── response.py         # Phase 5: Final response engine
├── llm/
│   ├── base.py         # LLMProvider — the single swappable abstraction
│   ├── gemini.py       # Google Gemini implementation
│   ├── nvidia.py       # NVIDIA OpenAI-compatible implementation
│   └── router.py       # Phase 2: multi-provider routing with fallback
├── tools/              # V1 tools: file_ops, apps, urls, clipboard,
│   │                   #   screenshot, sysinfo — each with input/output schemas
│   ├── execution.py    # ToolExecutor — safe execution boundary
│   ├── filesystem.py   # Phase 4: controlled filesystem tools with security
│   └── command.py      # Phase 4: controlled command execution with blocking
├── actions/
│   ├── __init__.py     # PermissionGate (V1 pass-through)
│   ├── audit_log.py    # append-only audit log
│   └── permissions.py  # Phase 2: SecurePermissionGate with confirmation
├── core/
│   ├── agent.py        # text-in → model → tool dispatch → text-out
│   ├── brain.py        # orchestrator (uses Pipeline internally)
│   └── router.py       # intent classification (deterministic + optional LLM)
├── memory/
│   ├── __init__.py     # in-process Memory (Phase 1)
│   ├── persistent.py   # Phase 2: file-backed PersistentMemory
│   └── semantic.py     # Phase 3: keyword-based SemanticMemory with retrieval
└── agents/             # Phase 3: specialized agent architecture
    ├── __init__.py     # BaseAgent, AgentRegistry, AgentSpec
    ├── research.py     # ResearchAgent for information gathering
    ├── coding.py       # CodingAgent for code analysis/generation
    └── task.py         # TaskAgent for multi-step execution
```

### Phase 5 Orchestration Flow

```
User Request
      ↓
1. Goal Engine → Goal (normalize, analyze complexity, detect capabilities)
      ↓
2. Goal Planner → TaskGraph (decompose into tasks with dependencies)
      ↓
3. Agent Manager → assign agents by capability
      ↓
4. Orchestrator → execute tasks (parallel where independent)
      ↓
5. Tool Execution → Phase 4 security/permission/audit layer
      ↓
6. Verification Engine → verify task outputs
      ↓
7. Recovery → retry/replan on failure
      ↓
8. Context Management → bounded, layered context
      ↓
9. Response Engine → structured final result
      ↓
10. Final Response (SUCCESS / PARTIAL / FAILED / BLOCKED)
```

### Pipeline Flow

```
User Request
      ↓
1. Normalize input
      ↓
2. Route (CONVERSATIONAL / TOOL / AGENT / UNSUPPORTED)
      ↓
3. Build plan (if tool/agent route)
      ↓
4. Execute via agent loop
      ↓
5. Verify results (structural + semantic)
      ↓
6. Return structured PipelineResult
```

### Error Hierarchy

```
JarvisError (base)
├── ConfigurationError
├── ProviderError
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── TimeoutError
│   └── MalformedResponseError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolAlreadyExistsError
│   ├── InvalidToolError
│   ├── InvalidParametersError
│   ├── PermissionDeniedError
│   └── ToolExecutionError
├── VerificationError
└── ExecutionError
```

## Phase 2 Features

### Persistent Memory

Conversation history is saved to a JSON-lines file and loaded on startup. Sessions are automatically detected by timestamp gaps.

```powershell
# Enable persistence
ULTRON_MEMORY_FILE=~/.ultron/memory.jsonl

# Check status in REPL
ultron> /memory
```

### Permissioned Execution

Mutating tools require user confirmation before execution.

```powershell
# Enable permission prompts
ULTRON_REQUIRE_PERMISSION=true

# Check status in REPL
ultron> /permissions
```

### Multi-Provider Routing

If the primary provider fails, the router automatically falls back to the next provider.

```powershell
# Set up fallback chain
ULTRON_PROVIDER=gemini
ULTRON_PROVIDER_FALLBACK=nvidia
```

## Phase 3 Features

### Semantic Memory

Keyword-based retrieval with relevance ranking. Memory records include metadata (type, importance, source) and are indexed for fast search.

```python
from ultron.memory.semantic import SemanticMemory
from ultron.models import MemoryType

memory = SemanticMemory("~/.ultron/memory.jsonl")
memory.add_with_metadata("user", "Python tutorial", MemoryType.FACT, importance=0.8)
results = memory.search("Python programming", limit=5)
```

### Multi-step Planning

Plans with explicit dependencies, retry limits, and cycle detection.

```python
from ultron.planner import Planner, PlanExecutor
from ultron.models import MultiStepPlanStep

planner = Planner()
steps = [
    MultiStepPlanStep(objective="Read config", tool_name="read_file", arguments={"path": "config.json"}),
    MultiStepPlanStep(objective="Write output", tool_name="create_file", dependencies=[step1.step_id]),
]
plan = planner.create_plan(steps)
executor = PlanExecutor(tool_executor)
result = executor.execute_plan(plan)
```

### Specialized Agents

Three specialized agents for different task types:

- **ResearchAgent**: Information gathering, source analysis, evidence collection
- **CodingAgent**: Code analysis, implementation planning, test generation
- **TaskAgent**: General multi-step execution, plan following

```python
from ultron.agents import AgentRegistry, AgentCapability
from ultron.agents.research import ResearchAgent

registry = AgentRegistry()
registry.register(ResearchAgent(provider, tools))
agent = registry.select(AgentCapability.RESEARCH)
result = agent.run("research this topic")
```

### Semantic Verification

Verifies if execution results satisfy objectives using keyword matching.

```python
from ultron.verification import SemanticVerifier
from ultron.models import ExecutionResult, ExecutionStatus

verifier = SemanticVerifier()
result = ExecutionResult(tool_name="tool", status=ExecutionStatus.SUCCESS, output={"content": "Python tutorial"})
verification = verifier.verify(result, objective="read file", expected_keywords=["python"])
```

## Phase 4 Features

### Risk Classification

Every tool operation is classified by risk level: READ, LOW, MEDIUM, HIGH, CRITICAL.

```python
from ultron.risk import RiskClassifier, RiskLevel

classifier = RiskClassifier()
risk = classifier.classify("delete_file")  # RiskLevel.HIGH
```

### Permission Policy Engine

Risk-based policies control tool execution: ALLOW, CONFIRM, DENY.

```python
from ultron.policy import PolicyEngine, PolicyAction
from ultron.risk import RiskLevel

engine = PolicyEngine(confirm_callback=lambda t, a, r: True)
allowed = engine.request_permission("create_file", RiskLevel.MEDIUM)
```

### Controlled Filesystem Tools

Secure filesystem operations with path validation and allowed-root restrictions.

```python
from ultron.tools.filesystem import FilesystemTool

fs = FilesystemTool(allowed_roots=["/path/to/workspace"])
fs.create_file("test.txt", "content")
fs.read_file("test.txt")
fs.delete_file("test.txt")
```

### Controlled Command Execution

System command execution with timeout, blocking, and structured results.

```python
from ultron.tools.command import CommandExecutor

executor = CommandExecutor(timeout=10, blocked_commands=["format"])
result = executor.execute("echo hello")
print(result.stdout, result.exit_code)
```

### Sandbox Execution

Isolated execution environments for risky operations.

```python
from ultron.sandbox import LocalSandbox

with LocalSandbox() as sandbox:
    result = sandbox.execute("echo sandboxed")
    print(result.stdout)
```

### Browser Automation

Abstracted browser operations with permission enforcement.

```python
from ultron.browser import BrowserTool

browser = BrowserTool()
browser.navigate("https://example.com")
page = browser.read_page()
print(page.data["text"])
```

### Execution State Persistence

Task state survives interruptions for recovery.

```python
from ultron.execution_state import ExecutionStateStore, TaskState

store = ExecutionStateStore("~/.ultron/execution_state.json")
task = TaskState(task_id="t1", description="my task")
store.save_task(task)
```

### Recovery and Replanning

Controlled recovery from failures with retry limits.

```python
from ultron.recovery import RecoveryEngine

engine = RecoveryEngine(max_retries=3)
decision = engine.decide_recovery(step, TimeoutError("timeout"))
```

### Audit Event System

Structured execution logging for observability.

```python
from ultron.audit import AuditLogger

audit = AuditLogger("~/.ultron/audit_events.jsonl")
audit.log_tool_executed("r1", "read_file", True, 10.5)
trace = audit.get_trace("r1")
```

### Streaming Execution Status

Real-time progress reporting for CLI/UI interfaces.

```python
from ultron.status import StatusReporter, CallbackSubscriber

reporter = StatusReporter()
reporter.subscribe(CallbackSubscriber(lambda u: print(u.message)))
reporter.task_started("t1", "processing")
reporter.completed("t1")
```

## Phase 5 Features

### Goal Engine

Converts user requests into structured Goal objects with complexity assessment, capability detection, and success criteria extraction.

```python
from ultron.goal import GoalEngine, GoalComplexity

engine = GoalEngine()
goal = engine.create_goal("Research Python frameworks and create a comparison report")
print(goal.complexity)  # MODERATE or COMPLEX
print(goal.required_capabilities)  # ['research', 'analysis', 'writing']
print(goal.success_criteria)  # [SuccessCriteria(...)]
```

### Task Graph

Dependency-aware task graph with cycle detection, ready-task discovery, and parallel execution support.

```python
from ultron.task import Task, TaskGraph, TaskStatus

graph = TaskGraph(goal_id="g1")
t1 = Task(id="t1", description="Research")
t2 = Task(id="t2", description="Analyze", dependencies=["t1"])
t3 = Task(id="t3", description="Report", dependencies=["t1", "t2"])
graph.add_task(t1)
graph.add_task(t2)
graph.add_task(t3)

print(graph.ready_tasks())  # [t1]
graph.on_task_completed("t1")
print(graph.ready_tasks())  # [t2]
print(graph.get_parallel_groups())  # [[t1], [t2], [t3]]
```

### Goal Planner

Converts Goals into TaskGraphs with minimal decomposition for simple requests and full decomposition for complex ones.

```python
from ultron.planner_v5 import GoalPlanner
from ultron.goal import GoalEngine

engine = GoalEngine()
planner = GoalPlanner()

goal = engine.create_goal("Research and create a report")
graph = planner.plan(goal)
print(graph.task_count)  # Number of tasks created
print(graph.validate())  # [] if valid
```

### Agent Manager

Capability-based agent selection with availability tracking and structured communication protocol.

```python
from ultron.agent_manager import AgentManager, AgentMessage, MessageType

manager = AgentManager()
# Register agents...
selected = manager.select_agent(["research", "analysis"])
manager.mark_busy(selected.spec.name, "task-1")

# Structured messaging
msg = AgentMessage.task_request(
    sender="orchestrator",
    receiver="research",
    task_id="t1",
    task_description="Research Python frameworks",
)
```

### Verification Engine

Structured verification with multiple check types: status, output keys, file existence, content matching, and custom checkers.

```python
from ultron.verification_v5 import VerificationEngine, VerificationCheck, VerificationCheckType
from ultron.models import ExecutionResult, ExecutionStatus

engine = VerificationEngine()
result = ExecutionResult(tool_name="create_file", status=ExecutionStatus.SUCCESS, output={"created": True})
checks = [
    VerificationCheck(check_type=VerificationCheckType.STATUS, description="check status"),
    VerificationCheck(check_type=VerificationCheckType.OUTPUT_KEYS, expected_value=["created"]),
]
verification = engine.verify_task("t1", result, checks)
print(verification.overall_passed)  # True
print(verification.confidence)  # 1.0
```

### Context Management

Bounded, layered context for goal/task/agent/execution layers. Prevents uncontrolled context growth.

```python
from ultron.context import ContextManager, GoalContext, TaskContext

mgr = ContextManager()
mgr.set_goal_context(GoalContext(goal_id="g1", goal_description="Research"))
mgr.set_task_context("t1", TaskContext(task_id="t1", objective="Gather data"))
prompt = mgr.build_agent_prompt_context(mgr.get_task_context("t1"))
```

### Final Response Engine

Generates structured results with outcome classification: SUCCESS, PARTIAL_SUCCESS, FAILED, BLOCKED.

```python
from ultron.response import ResponseEngine, ResponseOutcome
from ultron.goal import Goal
from ultron.task import TaskGraph

engine = ResponseEngine()
goal = Goal(description="test", original_request="do test")
graph = TaskGraph(goal_id=goal.id)
result = engine.generate(goal, graph)
print(result.outcome)  # ResponseOutcome.SUCCESS
print(result.summary)  # "Goal completed successfully..."
```

### Execution Orchestrator

Central orchestration loop that coordinates Goal → Plan → Execute → Verify → Recover → Respond.

```python
from ultron.orchestrator import Orchestrator, OrchestratorConfig

orch = Orchestrator(
    tool_executor=executor,
    config=OrchestratorConfig(enable_parallel_execution=True),
)
result = orch.execute_goal("Create a file with test content and verify it exists")
print(result.goal_result.outcome)  # SUCCESS / PARTIAL / FAILED / BLOCKED
```

## Extension points (by design)

- **Provider swap**: implement `LLMProvider` and add one branch in `ultron/llm/__init__.py:build_provider`. No routing logic exists; `ULTRON_PROVIDER` selects the single upstream.
- **Multi-provider routing**: use `ProviderRouter` to wrap multiple providers with automatic fallback.
- **Permissions**: `SecurePermissionGate` uses a callback for confirmation — CLI uses `input()`, other frontends can use their own mechanisms.
- **Specialized agents**: subclass `BaseAgent` and register with `AgentRegistry` to add new capabilities.
- **Risk policies**: customize `RiskClassifier` and `PolicyEngine` for different risk profiles.
- **Sandbox**: implement `Sandbox` abstract class for containerized execution.
- **Browser**: implement `BrowserSession` and `BrowserPage` for real browser automation.
- **Audit**: extend `AuditLogger` for custom event types and storage backends.
- **Voice (later)**: `core.agent.Agent.run(text) -> RunResult` is UI-agnostic — a voice layer consumes the same object.

## Security Limitations

Phase 4 provides controlled execution but has important limitations:

- **Filesystem**: Path validation prevents traversal but relies on configured allowed roots
- **Commands**: Blocked commands are pattern-matched, not comprehensive
- **Sandbox**: LocalSandbox provides process isolation, not VM isolation
- **Browser**: Mock implementation only; real browser automation requires additional libraries
- **Permissions**: Policy engine is configurable, not foolproof
- **LLM**: The LLM is not the security boundary — tool/policy/sandbox layers are

For production use, consider:
- Restricting allowed filesystem roots to specific directories
- Using RestrictedSandbox or containerized sandboxes
- Implementing real browser automation with Playwright/Selenium
- Adding network security policies
- Monitoring audit logs for suspicious patterns

## V1 tools

| Tool | Mutates | What it does |
| --- | --- | --- |
| `read_file` | no | read text file (+size/mtime/encoding) |
| `create_file` | yes | write text file (refuses overwrite unless asked) |
| `search_files` | no | glob search in a directory |
| `open_app` | yes | launch known app or .exe path |
| `close_app` | yes | stop a running process by name |
| `open_url` | yes | open http/https URL in default browser |
| `get_clipboard` / `set_clipboard` | yes* | read/replace clipboard text |
| `take_screenshot` | yes* | capture primary screen to PNG |
| `get_system_info` | no | OS/CPU/RAM/disk/uptime |

(* state-changing, so they are audit-logged too.)

## Adding a tool

1. Create a new file in `ultron/tools/` (or add to an existing file)
2. Subclass `Tool` and implement `name`, `description`, `parameters`, `output_schema`, and `run()`
3. Register it in `ultron/tools/__init__.py` in the `ALL_TOOLS` list
4. Add keyword mappings in `ultron/core/router.py` `TOOL_KEYWORD_MAP` for deterministic routing
5. Write tests

## Adding an LLM provider

1. Create a new file in `ultron/llm/`
2. Subclass `LLMProvider` and implement `complete()`, `feed_tool_results()`, and `health_check()`
3. Add a branch in `ultron/llm/__init__.py:build_provider()`
4. Add the provider name to `SUPPORTED_PROVIDERS` in `config.py`
5. Add config fields if needed
6. Write tests
>>>>>>> b26fbe8 (Initial Ultron project - JARVIS-style desktop assistant v0.1.0)
