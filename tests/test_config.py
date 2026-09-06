"""Tests for config loading — env resolution, defaults, and errors."""

from __future__ import annotations

import pytest

from ultron.config import ConfigError, load_config, load_dotenv


def test_load_dotenv_basic(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ULTRON_PROVIDER=gemini\n"
        "GEMINI_API_KEY=abc123\n"
        "# comment\n"
        "ULTRON_MODEL=\"gemini-3.5-flash\"\n"
        "EMPTY=\n",
        encoding="utf-8",
    )
    env = load_dotenv(env_file)
    assert env["GEMINI_API_KEY"] == "abc123"
    assert env["ULTRON_MODEL"] == "gemini-3.5-flash"
    assert "comment" not in env
    assert env.get("EMPTY") == ""


def test_defaults_and_override(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from_dotenv\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.provider == "gemini"
    assert config.gemini_api_key == "from_dotenv"
    assert config.model == "gemini-3.5-flash"
    assert config.max_tool_iterations == 8

    config2 = load_config(env_file, environ={"GEMINI_API_KEY": "from_env", "ULTRON_MODEL": "gemini-3.6-flash"})
    assert config2.gemini_api_key == "from_env"
    assert config2.model == "gemini-3.6-flash"


def test_missing_api_key_raises(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ULTRON_PROVIDER=gemini\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        load_config(env_file, environ={})


def test_unsupported_provider_raises(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ULTRON_PROVIDER=unsupported_provider\nGEMINI_API_KEY=x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not supported"):
        load_config(env_file, environ={})


def test_missing_env_file_uses_defaults_and_fails_on_key(tmp_path):
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        load_config(tmp_path / "nonexistent.env", environ={})


def test_audit_path_expansion(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_AUDIT_LOG=~/custom/ultron.log\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert str(config.audit_log_path) == str(config.audit_log_path.expanduser())


def test_bad_int_value_raises(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_MAX_TOOL_ITERATIONS=banana\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="integer"):
        load_config(env_file, environ={})


def test_debug_mode_sets_log_level(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_DEBUG=true\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.debug_mode is True
    assert config.log_level == "DEBUG"


def test_debug_mode_false_by_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.debug_mode is False
    assert config.log_level == "INFO"


def test_api_base_url(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_API_BASE_URL=https://custom.api.com\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.api_base_url == "https://custom.api.com"


def test_api_base_url_default_empty(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.api_base_url == ""


def test_tool_timeout(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_TOOL_TIMEOUT=30\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.tool_timeout == 30


def test_tool_timeout_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\n", encoding="utf-8")
    config = load_config(env_file, environ={})
    assert config.tool_timeout == 60


def test_bad_tool_timeout_raises(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=x\nULTRON_TOOL_TIMEOUT=banana\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="integer"):
        load_config(env_file, environ={})


def test_sub_config_grouping(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=test_key\nULTRON_MODEL=gemini-3.5-flash\n", encoding="utf-8")
    config = load_config(env_file, environ={})

    assert config.llm.provider == "gemini"
    assert config.llm.gemini_api_key == "test_key"
    assert config.llm.model == "gemini-3.5-flash"
    assert config.memory.enabled is True
    assert config.security.permission_policy == "default"
    assert config.execution.max_tool_iterations == 8
