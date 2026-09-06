"""Phase 1 logging + CLI contract.

Verifies:
  * configure_logging is idempotent and respects the level string
  * the formatter redacts *_KEY/TOKEN/SECRET/PASSWORD assignments
  * Cli accepts bare `exit | quit | shutdown` (spec requirement)

The CLI is exercised via `Cli._dispatch`, the same entry point the REPL
loop uses, so the bare-exit path is pinned without spawning a subprocess.
"""

from __future__ import annotations

import logging

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.cli import Cli
from ultron.core.agent import Agent
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.logging_setup import LOGGER_NAME, configure_logging, get_logger
from ultron.memory import Memory
from ultron.tools import ALL_TOOLS, ToolRegistry


class _StubProvider(LLMProvider):
    name = "stub"

    def complete(self, text, tools):
        return ProviderResult(text="ok", tool_calls=[])

    def feed_tool_results(self, results):
        pass


def _make_cli(tmp_path):
    provider = _StubProvider()
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
    )
    return Cli(agent=agent, memory=Memory(), registry=registry)


def test_configure_logging_sets_level():
    root = configure_logging("DEBUG")
    assert root.level == logging.DEBUG
    configure_logging("ERROR")
    assert root.level == logging.ERROR
    configure_logging("INFO")
    assert root.level == logging.INFO


def test_configure_logging_unknown_level_falls_back_to_info():
    root = configure_logging("not-a-level")
    assert root.level == logging.INFO


def test_logger_name_under_ultron_hierarchy():
    child = get_logger("ultron.brain")
    assert child.name == "ultron.brain"
    assert child.name.startswith(LOGGER_NAME)


def test_secret_redaction_in_formatter(caplog):
    from ultron.logging_setup import _SecretRedactingFormatter

    formatter = _SecretRedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Create a log record with secrets
    record = logging.LogRecord(
        name="ultron.test_redact",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="loaded config API_KEY=SECRET_ABCDEF token=topsecret value=harmless",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    # The formatted line must not contain the secret strings
    assert "SECRET_ABCDEF" not in formatted
    assert "topsecret" not in formatted
    # Non-secret values must survive
    assert "harmless" in formatted


def test_cli_bare_exit_commands(tmp_path):
    cli = _make_cli(tmp_path)
    assert cli._dispatch("exit") is False
    assert cli._dispatch("quit") is False
    assert cli._dispatch("shutdown") is False
    # /exit still works
    assert cli._dispatch("/exit") is False
    # Non-exit lines should not return False
    assert cli._dispatch("/help") is None
