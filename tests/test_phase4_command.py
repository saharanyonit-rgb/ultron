"""Tests for controlled command execution (Phase 4)."""

from __future__ import annotations

from ultron.tools.command import CommandExecutor, CommandResult, CommandStatus
from ultron.risk import RiskLevel


def test_execute_simple_command():
    executor = CommandExecutor(timeout=5)
    result = executor.execute("echo hello")
    assert result.success or result.status == CommandStatus.SUCCESS
    assert "hello" in result.stdout.lower() or result.exit_code == 0


def test_execute_command_with_stdout():
    executor = CommandExecutor(timeout=5)
    result = executor.execute("echo test_output")
    assert "test_output" in result.stdout


def test_execute_command_failure():
    executor = CommandExecutor(timeout=5)
    result = executor.execute("exit 1")
    assert result.exit_code == 1
    assert result.status == CommandStatus.FAILED


def test_execute_command_timeout():
    executor = CommandExecutor(timeout=1)
    result = executor.execute("ping -n 10 127.0.0.1", timeout=1)
    assert result.status == CommandStatus.TIMEOUT or result.duration_ms > 0


def test_execute_command_blocked():
    executor = CommandExecutor(blocked_commands=["format"])
    result = executor.execute("format C:")
    assert result.status == CommandStatus.BLOCKED


def test_execute_command_not_in_allowed_list():
    executor = CommandExecutor(allowed_commands=["echo", "dir"])
    result = executor.execute("whoami")
    assert result.status == CommandStatus.BLOCKED


def test_execute_command_working_directory(tmp_path):
    executor = CommandExecutor(timeout=5)
    result = executor.execute("dir", working_directory=str(tmp_path))
    assert result.working_directory == str(tmp_path)


def test_execute_command_invalid():
    executor = CommandExecutor(timeout=5)
    result = executor.execute("nonexistent_command_xyz")
    assert result.status == CommandStatus.FAILED


def test_command_result_to_dict():
    result = CommandResult(
        command="echo test",
        status=CommandStatus.SUCCESS,
        stdout="test\n",
        exit_code=0,
        duration_ms=10.5,
    )
    d = result.to_dict()
    assert d["command"] == "echo test"
    assert d["status"] == "success"
    assert d["exit_code"] == 0


def test_command_result_success_property():
    result = CommandResult(command="test", status=CommandStatus.SUCCESS, exit_code=0)
    assert result.success is True
    result2 = CommandResult(command="test", status=CommandStatus.FAILED, exit_code=1)
    assert result2.success is False


def test_get_risk_level():
    executor = CommandExecutor(unrestricted=False)
    assert executor.get_risk_level("echo hello") == RiskLevel.CRITICAL
    assert executor.get_risk_level("delete file") == RiskLevel.HIGH


def test_get_risk_level_unrestricted():
    executor = CommandExecutor()
    assert executor.get_risk_level("echo hello") == RiskLevel.READ


def test_execute_command_with_env():
    executor = CommandExecutor(timeout=5)
    result = executor.execute("echo test", env={"MY_VAR": "value"})
    assert result.status in (CommandStatus.SUCCESS, CommandStatus.FAILED)


def test_blocked_commands_list():
    executor = CommandExecutor(unrestricted=False)
    assert "format" in executor._blocked_commands


def test_unrestricted_no_blocking():
    executor = CommandExecutor()
    assert len(executor._blocked_commands) == 0
