"""Tests for Ultron terminal CLI — `ultron.cli`."""

from __future__ import annotations

import pytest

from ultron.actions import PermissionGate
from ultron.actions.audit_log import AuditLog
from ultron.cli import Cli, main
from ultron.core.agent import Agent
from ultron.llm.base import LLMProvider, ProviderResult
from ultron.memory import Memory
from ultron.tools import ALL_TOOLS, ToolRegistry


class ScriptedProvider(LLMProvider):
    name = "scripted"

    def complete(self, text, tools):
        return ProviderResult(text="response from scripted provider")

    def feed_tool_results(self, results):
        pass


def test_cli_dispatch_commands(tmp_path, capsys):
    provider = ScriptedProvider()
    registry = ToolRegistry(ALL_TOOLS)
    audit = AuditLog(tmp_path / "audit.log")
    agent = Agent(
        provider=provider,
        tools=registry.all(),
        audit_log=audit,
        gate=PermissionGate(),
    )
    memory = Memory()
    cli = Cli(agent=agent, memory=memory, registry=registry)

    # Exit commands return False
    assert cli._dispatch("/exit") is False
    assert cli._dispatch("/quit") is False

    # Help command prints help text
    cli._dispatch("/help")
    captured = capsys.readouterr()
    assert "/tools" in captured.out

    # Clear command clears memory
    memory.add("user", "hello")
    assert len(memory) == 1
    cli._dispatch("/clear")
    assert len(memory) == 0

    # Normal line runs through agent and stores in memory
    cli._dispatch("hello ultron")
    assert len(memory) == 2
    assert memory.all()[0].content == "hello ultron"
    assert memory.all()[1].content == "response from scripted provider"


def test_main_missing_env_returns_error_code(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ULTRON_PROVIDER", "gemini")
    # Missing API key should cause provider initialization to fail
    code = main([])
    assert code == 1
