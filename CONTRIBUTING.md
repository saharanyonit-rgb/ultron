# Contributing to Ultron / JARVIS
## Dev Setup
```powershell
git clone https://github.com/saharanyonit-rgb/ultron.git
cd ultron
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```
Verify:
```powershell
python -m pytest tests/ -v -m "not real_e2e"
python -m ultron
```
---
## Adding a New Tool
1. Create `ultron/tools/my_tool.py` subclassing `Tool`
2. Register in `ultron/tools/__init__.py`
3. Add keywords to `ultron/core/router.py` under `TOOL_KEYWORD_MAP`
4. Add to `hiddenimports` in `jarvis.spec`
5. Write tests in `tests/test_my_tool.py`
## Adding a New LLM Provider
1. Create `ultron/llm/my_provider.py` subclassing `LLMProvider`
2. Implement `complete()` and `feed_tool_results()`
3. Add branch in `ultron/llm/__init__.py:build_provider()`
4. Add to `SUPPORTED_PROVIDERS` in `ultron/config.py`
5. Document env vars in `.env.example`
## Adding a New Brain
1. Create `ultron/brains/my_brain.py`
2. Register in `ultron/brains/__init__.py`
3. Add config in `BrainConfig` (`ultron/config.py`)
4. Document in `.env.example`
---
## Running Tests
```powershell
# Fast unit tests (no API keys needed)
python -m pytest tests/ -v -m "not real_e2e"
# With coverage
python -m pytest tests/ --cov=ultron --cov-report=term-missing -m "not real_e2e"
# Real E2E (requires API keys, costs tokens)
python -m pytest tests/ -v -m "real_e2e"
```
---
## Code Style
```powershell
pip install ruff
ruff check ultron/ desktop/
ruff format ultron/ desktop/
```
- Python 3.12+ type hints everywhere
- `str | None` not `Optional[str]`
- Docstrings on every public class and method
---
## Submitting a PR
1. Fork and branch from `main`
2. Make changes, add tests
3. Ensure `pytest` and `ruff check` pass
4. Open a PR using the template
**Never commit `.env` files or API keys.**
