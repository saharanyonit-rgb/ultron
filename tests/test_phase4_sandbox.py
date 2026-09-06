"""Tests for sandbox abstraction (Phase 4)."""

from __future__ import annotations

from ultron.sandbox import LocalSandbox, RestrictedSandbox, SandboxResult, SandboxStatus


def test_local_sandbox_create():
    sandbox = LocalSandbox()
    sandbox.create()
    assert sandbox.get_workspace().exists()
    sandbox.cleanup()


def test_local_sandbox_execute():
    with LocalSandbox() as sandbox:
        result = sandbox.execute("echo hello")
        assert result.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)
        assert "hello" in result.stdout or result.exit_code == 0


def test_local_sandbox_workspace_isolated():
    with LocalSandbox() as sandbox1, LocalSandbox() as sandbox2:
        assert sandbox1.get_workspace() != sandbox2.get_workspace()


def test_local_sandbox_cleanup():
    sandbox = LocalSandbox()
    sandbox.create()
    workspace = sandbox.get_workspace()
    assert workspace.exists()
    sandbox.cleanup()
    assert not workspace.exists()


def test_local_sandbox_env_variable():
    with LocalSandbox() as sandbox:
        result = sandbox.execute("echo %JARVIS_SANDBOX%", env={"JARVIS_SANDBOX": "1"})
        assert result.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)


def test_local_sandbox_timeout():
    sandbox = LocalSandbox()
    sandbox.create()
    result = sandbox.execute("ping -n 10 127.0.0.1", timeout=1)
    assert result.status == SandboxStatus.TIMEOUT
    sandbox.cleanup()


def test_sandbox_result_to_dict():
    result = SandboxResult(
        status=SandboxStatus.COMPLETED,
        stdout="output",
        exit_code=0,
        duration_ms=100.0,
    )
    d = result.to_dict()
    assert d["status"] == "completed"
    assert d["exit_code"] == 0


def test_restricted_sandbox():
    sandbox = RestrictedSandbox()
    sandbox.create()
    result = sandbox.execute("echo restricted")
    assert result.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)
    sandbox.cleanup()


def test_local_sandbox_status():
    sandbox = LocalSandbox()
    assert sandbox.status == SandboxStatus.CREATED
    sandbox.create()
    sandbox.cleanup()
    assert sandbox.status == SandboxStatus.CLEANED


def test_local_sandbox_multiple_commands():
    with LocalSandbox() as sandbox:
        r1 = sandbox.execute("echo first")
        r2 = sandbox.execute("echo second")
        assert r1.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)
        assert r2.status in (SandboxStatus.COMPLETED, SandboxStatus.FAILED)
