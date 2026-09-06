"""Tests for the V1 tool set.

Tools that touch the real desktop (clipboard, screenshot, app launch) run
through PowerShell. They are safe to run here but each is isolated so a
failure doesn't cascade.
"""

from __future__ import annotations

import pytest

from ultron.tools import ALL_TOOLS
from ultron.tools.apps import CloseApp, OpenApp
from ultron.tools.clipboard import GetClipboard, SetClipboard
from ultron.tools.file_ops import CreateFile, ReadFile, SearchFiles
from ultron.tools.screenshot import TakeScreenshot
from ultron.tools.sysinfo import GetSystemInfo
from ultron.tools.urls import OpenUrl


def test_all_tools_have_valid_specs():
    assert ALL_TOOLS, "registry must not be empty"
    for tool in ALL_TOOLS:
        spec = tool.spec
        assert spec.name and spec.description, f"{tool} missing name/description"
        assert spec.parameters.get("type") == "object", f"{spec.name} parameters must be an object schema"
        assert spec.output_schema.get("type") == "object", f"{spec.name} output_schema must be an object schema"


def test_system_info_keys():
    result = GetSystemInfo().run()
    for key in ("os", "os_version", "hostname", "cpu", "cpu_cores", "ram_total_gb", "drives"):
        assert key in result, f"missing {key}"
    assert result["cpu_cores"] >= 1
    assert result["ram_total_gb"] > 0


def test_file_create_read_search_roundtrip(tmp_path):
    target = tmp_path / "sub" / "hello.txt"
    create = CreateFile().run(path=str(target), content="hello world")
    assert create.get("error") is None
    assert create["bytes_written"] == len("hello world")

    read = ReadFile().run(path=str(target))
    assert read["content"] == "hello world"

    again = CreateFile().run(path=str(target), content="nope")
    assert "already exists" in again["error"]

    overwrite = CreateFile().run(path=str(target), content="v2", overwrite=True)
    assert overwrite["bytes_written"] == 2
    assert ReadFile().run(path=str(target))["content"] == "v2"

    search = SearchFiles().run(directory=str(tmp_path), pattern="**/*.txt")
    assert search["count"] >= 1
    assert str(target) in search["matches"]


def test_read_missing_file_reports_error():
    assert "not found" in ReadFile().run(path="C:\\definitely-not-here-ultron\\x.txt")["error"]


def test_search_missing_directory_reports_error():
    assert "not found" in SearchFiles().run(directory="C:\\nope-ultron", pattern="*")["error"]


def test_open_url_rejects_unsafe_scheme():
    for bad in ("javascript:alert(1)", "file:///C:/Windows", "ftp://example.com"):
        result = OpenUrl().run(url=bad)
        assert "error" in result, f"{bad} must be rejected"


def test_open_app_unknown_name_errors_without_launching():
    result = OpenApp().run(app_name="definitely_not_an_app_ultron")
    assert "error" in result
    assert "notepad" in result["error"]


def test_app_registry_known_names():
    for name in ("notepad", "calc", "explorer", "settings", "cmd"):
        tool = OpenApp()
        target, error = __import__("ultron.tools.apps", fromlist=["_resolve_app"])._resolve_app(name)
        assert error is None and target


def test_close_app_not_running_is_safe():
    result = CloseApp().run(app_name="ultron_definitely_not_running")
    assert "error" not in result


def test_clipboard_roundtrip():
    marker = "ultron-clipboard-test-\u00e9\u00fc"
    result = SetClipboard().run(text=marker)
    assert result.get("error") is None
    assert GetClipboard().run()["text"] == marker


def test_screenshot_writes_png(tmp_path):
    target = tmp_path / "shot.png"
    result = TakeScreenshot().run(path=str(target))
    assert result.get("error") is None, result
    assert target.is_file()
    assert target.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert result["width"] > 0 and result["height"] > 0
