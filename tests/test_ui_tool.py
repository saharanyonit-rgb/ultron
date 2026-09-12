"""Tests for the UI/UX design generator tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from ultron.tools import ALL_TOOLS, ToolRegistry
from ultron.tools.ui_tool import GenerateUI, OUTPUT_DIR


@pytest.fixture()
def ui_tool(tmp_path, monkeypatch):
    try:
        import ultron.tools.ui_tool as ui

        monkeypatch.setattr(ui, "OUTPUT_DIR", tmp_path)
    except Exception:
        pass
    return GenerateUI()


def test_generate_ui_creates_html_file(ui_tool):
    result = ui_tool.run("AI landing page for my startup")
    assert result["success"] is True
    out = Path(result["output_file"])
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "<style>" in text
    assert "@keyframes" in text
    assert result["title"] and result["preset"] == "jarvis"
    assert result["snippet"].startswith("```html")


def test_generate_ui_presets(ui_tool):
    for preset in ["neon", "glass", "minimal"]:
        result = ui_tool.run("dashboard", preset=preset)
        assert result["success"] is True
        text = Path(result["output_file"]).read_text(encoding="utf-8")
        assert "@keyframes" in text


def test_generate_ui_missing_description(ui_tool):
    result = ui_tool.run("")
    assert result["success"] is False
    assert "description" in result["error"].lower()


def test_generate_ui_unknown_preset(ui_tool):
    result = ui_tool.run("hello", preset="rainbow")
    assert result["success"] is False
    assert "preset" in result["error"].lower()


def test_generate_ui_custom_output(ui_tool, tmp_path):
    target = tmp_path / "custom" / "page.html"
    result = ui_tool.run("login card", output_file=str(target))
    assert result["success"] is True
    assert Path(result["output_file"]) == target
    assert target.exists()


def test_generate_ui_registered():
    registry = ToolRegistry(ALL_TOOLS)
    assert registry.exists("generate_ui")
    assert registry.get("generate_ui").mutates is True


def test_default_output_dir(tmp_path):
    assert str(OUTPUT_DIR).endswith("generated_ui")