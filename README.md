 # ULTRON — Complete Guide

A JARVIS-style personal AI desktop assistant for Windows.

## 1. What Ultron Is

Ultron is a terminal-callable, text-in/text-out AI desktop assistant designed for Windows.

It includes:

* Structured AI processing pipeline
* Verification layer
* Persistent memory
* Permission-controlled tool execution
* Multi-provider LLM routing
* Semantic memory
* Multi-step planning
* Specialized agent architecture
* Desktop and system tools

This repository contains the current **Phase 5 build**.

---

## 2. Software Required

Before installing Ultron, make sure you have:

* **Windows**
* **Python 3.12 or newer**
* **Git**
* Internet connection for supported cloud AI providers

Python requirement:

```text
Python >= 3.12
```

Ultron uses packages including:

```text
google-genai
httpx
pyautogui
pyttsx3
speechrecognition
```

The complete dependency configuration is defined in `pyproject.toml`.

---

## 3. How to Clone Ultron

Clone the repository:

```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
```

Enter the project directory:

```powershell
cd ultron
```

---

## 4. How to Create the Python Environment

Create a Python 3.12 virtual environment:

```powershell
py -3.12 -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install Ultron and its development dependencies:

```powershell
pip install -e ".[dev]"
```

After installation, verify Python:

```powershell
python --version
```

---

## 5. How to Configure API Keys Safely

Ultron uses environment variables for API credentials.

First, create your local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and add your own API key(s).

Example:

```env
GEMINI_API_KEY=your_api_key_here
ULTRON_PROVIDER=gemini
```

Other supported providers can be configured according to the provider configuration in the project.

### Security Rules

**Never commit `.env` to GitHub.**

API keys should never be hardcoded into Python source files.

Ultron loads credentials from:

1. System environment variables
2. `.env`

Real environment variables take precedence over `.env` values.

### Important

Never publish:

```text
.env
API keys
Access tokens
Passwords
Private credentials
Personal configuration containing secrets
```

The repository includes `.env.example` specifically so users can configure their own credentials safely.

---

## 6. How to Start Ultron

With the virtual environment activated, run:

```powershell
.\.venv\Scripts\python -m ultron
```

Ultron starts in its terminal REPL.

### REPL Commands

Available commands include:

```text
/help
/tools
/history
/clear
/permissions
/memory
/exit
```

### Example

```text
ultron> what's my CPU and free disk space?
```

Ultron can select the appropriate system tool:

```text
[ran] get_system_info {}
```

Another example:

```text
ultron> create a file with "buy milk"
```

For permission-controlled operations, Ultron may ask for confirmation:

```text
[permission] Allow 'create_file'? [y/N]:
```

After confirmation:

```text
[ran] create_file {...}
```

---

## 7. How to Run Tests

Run the test suite with:

```powershell
.\.venv\Scripts\python -m pytest
```

The project contains a large automated test suite covering the Ultron architecture and its different phases.

Tests use mocked or fake providers where appropriate, so the standard test suite does not require live network access.

Real end-to-end tests are marked separately with `real_e2e` and are excluded from the default test run.

To run the standard test suite:

```powershell
.\.venv\Scripts\python -m pytest
```

---

## 8. Troubleshooting Common Errors

| Error                                 | Solution                                                                                                             |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError`                 | Make sure the virtual environment is activated and dependencies are installed.                                       |
| API key errors                        | Check that `.env` contains the required API key or that the corresponding system environment variable is configured. |
| `ULTRON_PROVIDER` not set             | Set a supported provider in `.env`, for example `ULTRON_PROVIDER=gemini`.                                            |
| Permission prompts                    | Confirm the requested action in the REPL when prompted.                                                              |
| Tests report no provider              | Check that `ULTRON_PROVIDER` is configured and the required API credentials are available.                           |
| Virtual environment will not activate | Try running PowerShell with the appropriate execution policy for the current session, then activate `.venv` again.   |
| Dependencies are missing              | Activate `.venv` and run `pip install -e ".[dev]"` again.                                                            |

---

## Project Structure

```text
ultron/
├── agents/          # Specialized agents
├── brains/          # Core AI reasoning and routing
├── core/            # Core assistant architecture
├── llm/             # LLM provider integrations
├── memory/          # Persistent and semantic memory
├── services/        # Assistant services
├── tools/           # Desktop and system tools
├── windows/         # Windows-specific functionality
└── ...

frontend/             # Ultron web interface
tests/                # Automated tests

.env.example          # Safe environment configuration template
.gitignore            # Files excluded from Git
pyproject.toml        # Project configuration
requirements.txt      # Runtime dependencies
requirements-dev.txt  # Development dependencies
uv.lock               # Dependency lock file
```

---

## Security

Ultron can interact with desktop and system resources, so security and permission control are important parts of the architecture.

Before running Ultron:

* Review the configured tools.
* Keep API credentials private.
* Do not commit `.env`.
* Do not expose credentials in logs or source code.
* Review permission settings before enabling automated actions.

---

## License

Add the project's license information here before publishing the repository publicly.
