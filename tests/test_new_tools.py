"""Tests for the Windows desktop, scheduling, and data/browser tool modules.

The Windows module only registers on Windows (via its `get_tools` factory), so
its tests are skipped elsewhere. The scheduling tests pin the two safety rules
that unattended execution depends on: CRITICAL tools cannot be deferred without
an explicit opt-in, and deferred work goes through the injected executor rather
than a self-built one.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from ultron.platform import is_windows
from ultron.risk import RiskLevel
from ultron.tools.catalog import default_catalog

requires_windows = pytest.mark.skipif(not is_windows(), reason="Windows-only tools")


# ── Windows desktop tools ────────────────────────────────────────────
@requires_windows
class TestWindowsDesktop:
    def test_windows_tools_are_registered(self):
        catalog = default_catalog()
        names = {n for n, m in catalog.metadata.items() if m.category == "windows"}
        assert {
            "list_windows",
            "get_active_window",
            "list_processes",
            "kill_process",
            "lock_workstation",
            "empty_recycle_bin",
            "list_displays",
            "get_battery_status",
            "show_desktop_notification",
            "open_windows_tool",
            "set_system_volume",
        } <= names

    def test_destructive_windows_tools_are_not_under_rated(self):
        catalog = default_catalog()
        # Killing a process, wiping the recycle bin and locking the session all
        # have consequences the user cannot trivially undo.
        for name in ("kill_process", "empty_recycle_bin"):
            assert catalog.risk_of(name) in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_kill_process_rejects_bad_pids(self):
        from ultron.tools.windows_desktop import KillProcess

        tool = KillProcess()
        assert "error" in tool.run(pid=0)
        assert "error" in tool.run(pid=-5)
        assert "error" in tool.run(pid="not-an-int")

    def test_kill_process_refuses_its_own_pid(self):
        import os

        from ultron.tools.windows_desktop import KillProcess

        assert "error" in KillProcess().run(pid=os.getpid())

    def test_open_windows_tool_rejects_unknown_target(self):
        from ultron.tools.windows_desktop import OpenWindowsTool

        result = OpenWindowsTool().run(target="definitely-not-a-target")
        assert "error" in result
        assert "expected one of" in result["error"]

    def test_open_windows_tool_rejects_bad_explorer_path(self):
        from ultron.tools.windows_desktop import OpenWindowsTool

        assert "error" in OpenWindowsTool().run(target="explorer", path="C:/definitely/missing")

    def test_set_system_volume_requires_an_argument(self):
        from ultron.tools.windows_desktop import SetSystemVolume

        assert "error" in SetSystemVolume().run()

    def test_list_displays_returns_geometry(self):
        from ultron.tools.windows_desktop import ListDisplays

        result = ListDisplays().run()
        assert "error" not in result, result
        assert result["count"] >= 1
        assert result["displays"][0]["width"] > 0

    def test_list_windows_returns_rows(self):
        from ultron.tools.windows_desktop import ListWindows

        result = ListWindows().run()
        assert "error" not in result, result
        assert result["count"] == len(result["windows"])

    def test_battery_status_handles_missing_battery(self):
        """Desktops have no battery; that must be reported, not raised."""
        from ultron.tools.windows_desktop import GetBatteryStatus

        result = GetBatteryStatus().run()
        assert "error" not in result, result
        if result["available"]:
            assert 0 <= result["percent"] <= 100
        else:
            assert result["note"]


# ── scheduling ───────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, output=None, error=None, allowed=True):
        self.output = output or {}
        self.error = error
        self.allowed = allowed
        self.status = "success" if not error else "failure"


class _FakeExecutor:
    """Records dispatches so tests can prove the injected executor is used."""

    def __init__(self, fail_tools=()):
        self.calls: list[tuple[str, dict]] = []
        self._fail = set(fail_tools)

    def execute(self, tool_name, arguments):
        self.calls.append((tool_name, dict(arguments or {})))
        if tool_name in self._fail:
            return _FakeResult({"error": "boom"}, error="boom", allowed=True)
        return _FakeResult({"ok": True})


@pytest.fixture
def scheduler(tmp_path, monkeypatch):
    """An isolated scheduler: own state file, own singleton, no live thread."""
    import ultron.tools.scheduling as module

    monkeypatch.setenv("ULTRON_SCHEDULE_FILE", str(tmp_path / "sched.json"))
    monkeypatch.setattr(module, "_SCHEDULER", None, raising=False)
    instance = module.TaskScheduler(path=tmp_path / "sched.json", tick_seconds=3600)
    monkeypatch.setattr(module, "_SCHEDULER", instance, raising=False)
    yield instance
    instance.stop()


class TestParseWhen:
    def test_relative_offsets(self):
        from ultron.tools.scheduling import parse_when

        for text, seconds in (("30s", 30), ("5m", 300), ("2h", 7200), ("1d", 86400)):
            delta = parse_when(text) - datetime.now().astimezone()
            assert abs(delta.total_seconds() - seconds) < 5

    def test_relative_offset_with_preposition(self):
        from ultron.tools.scheduling import parse_when

        assert parse_when("in 10 minutes") > datetime.now().astimezone()

    def test_clock_time_rolls_to_tomorrow_when_past(self):
        from ultron.tools.scheduling import parse_when

        now = datetime.now().astimezone()
        past = (now - timedelta(minutes=5)).strftime("%H:%M")
        result = parse_when(past)
        assert result.date() == (now + timedelta(days=1)).date()

    def test_iso_timestamp(self):
        from ultron.tools.scheduling import parse_when

        assert parse_when("2026-01-05T09:30").year == 2026

    def test_invalid_values_raise(self):
        from ultron.tools.scheduling import parse_when

        for bad in ("", "   ", "not-a-time", "sometime soon"):
            with pytest.raises(ValueError):
                parse_when(bad)


class TestScheduleTool:
    def test_critical_tools_cannot_be_deferred_by_default(self, scheduler):
        """Deferred work runs unattended, so CRITICAL needs an explicit opt-in."""
        from ultron.tools.scheduling import ScheduleTool

        result = ScheduleTool().run(tool_name="execute_command", when="30m",
                                    arguments={"command": "del /"})
        assert "error" in result
        assert "CRITICAL" in result["error"]

    def test_critical_opt_in_is_honoured(self, scheduler):
        from ultron.tools.scheduling import ScheduleTool

        result = ScheduleTool().run(tool_name="execute_command", when="30m",
                                    arguments={"command": "echo hi"}, allow_critical=True)
        assert "error" not in result
        assert result["risk"] == RiskLevel.CRITICAL.value

    def test_unknown_tool_is_rejected(self, scheduler):
        from ultron.tools.scheduling import ScheduleTool

        assert "error" in ScheduleTool().run(tool_name="no_such_tool", when="30m")

    def test_bad_time_is_rejected(self, scheduler):
        from ultron.tools.scheduling import ScheduleTool

        assert "error" in ScheduleTool().run(tool_name="take_screenshot", when="whenever")

    def test_high_and_lower_tools_are_schedulable(self, scheduler):
        from ultron.tools.scheduling import ScheduleTool

        result = ScheduleTool().run(tool_name="take_screenshot", when="30m")
        assert "error" not in result
        assert result["status"] == "pending"
        assert result["id"] in {t.id for t in scheduler.list_tasks()}

    def test_scheduled_task_persists(self, scheduler, tmp_path):
        from ultron.tools.scheduling import ScheduleTool, TaskScheduler

        ScheduleTool().run(tool_name="take_screenshot", when="30m")

        # A fresh scheduler over the same file proves it hit disk, not memory.
        reloaded = TaskScheduler(path=tmp_path / "sched.json", tick_seconds=3600)
        assert [t.tool_name for t in reloaded.list_tasks()] == ["take_screenshot"]


class TestSchedulerDispatch:
    def _due_task(self, scheduler, tool_name="take_screenshot", offset_seconds=-5):
        from ultron.tools.scheduling import ScheduledTask

        task = ScheduledTask(
            id="t1",
            tool_name=tool_name,
            arguments={"x": 1},
            run_at=(datetime.now().astimezone() + timedelta(seconds=offset_seconds)).isoformat(),
            risk="low",
            created_at=datetime.now().astimezone().isoformat(),
        )
        return scheduler.schedule(task)

    def test_due_tasks_are_dispatched_once(self, scheduler):
        executor = _FakeExecutor()
        scheduler.set_executor(executor)
        self._due_task(scheduler)

        assert scheduler.run_due() == 1
        assert executor.calls == [("take_screenshot", {"x": 1})]
        assert scheduler.run_due() == 0, "a settled task must not run twice"
        assert scheduler.list_tasks()[0].status == "completed"

    def test_future_tasks_do_not_run(self, scheduler):
        executor = _FakeExecutor()
        scheduler.set_executor(executor)
        self._due_task(scheduler, offset_seconds=3600)

        assert scheduler.run_due() == 0
        assert executor.calls == []

    def test_failure_is_recorded_not_raised(self, scheduler):
        class Boom:
            def execute(self, *_args, **_kwargs):
                raise RuntimeError("executor exploded")

        scheduler.set_executor(Boom())
        self._due_task(scheduler)
        assert scheduler.run_due() == 1
        task = scheduler.list_tasks()[0]
        assert task.status == "failed"
        assert "executor exploded" in (task.error or "")

    def test_cancel_only_works_while_pending(self, scheduler):
        task = self._due_task(scheduler, offset_seconds=3600)
        assert scheduler.cancel(task.id) is True
        assert scheduler.cancel(task.id) is False

    def test_executor_defaults_to_something_usable(self, scheduler):
        """A self-built fallback exists, but the entrypoints override it."""
        assert scheduler._get_executor() is not None  # noqa: SLF001


class TestAutomations:
    def _steps(self):
        return [
            {"tool_name": "get_system_info", "arguments": {}},
            {"tool_name": "take_screenshot", "arguments": {}},
        ]

    def test_create_and_list(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation, ListAutomations

        assert "error" not in CreateAutomation().run(name="morning", steps=self._steps())
        listed = ListAutomations().run()
        assert listed["count"] == 1
        assert listed["automations"][0]["steps"] == 2

    def test_duplicate_name_is_refused_then_overwritten(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation

        tool = CreateAutomation()
        assert "error" not in tool.run(name="morning", steps=self._steps())
        assert "error" in tool.run(name="morning", steps=self._steps())

        replaced = tool.run(name="morning", steps=self._steps()[:1], overwrite=True)
        assert "error" not in replaced
        assert replaced["steps"] == 1
        # Overwriting must keep the same id rather than accumulating duplicates.
        assert replaced["id"] == scheduler.get_automation("morning").id

    def test_unknown_tool_in_steps_is_rejected(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation

        result = CreateAutomation().run(name="bad", steps=[{"tool_name": "nope"}])
        assert "error" in result
        assert "nope" in result["error"]

    def test_empty_or_missing_steps_are_rejected(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation

        assert "error" in CreateAutomation().run(name="x", steps=[])
        assert "error" in CreateAutomation().run(name="", steps=self._steps())

    def test_run_executes_steps_in_order(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation, RunAutomation

        executor = _FakeExecutor()
        scheduler.set_executor(executor)
        CreateAutomation().run(name="morning", steps=self._steps())

        result = RunAutomation().run(name="morning")
        assert result["ok"] is True
        assert [c[0] for c in executor.calls] == ["get_system_info", "take_screenshot"]

    def test_run_stops_at_first_failure(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation, RunAutomation

        executor = _FakeExecutor(fail_tools={"take_screenshot"})
        scheduler.set_executor(executor)
        CreateAutomation().run(
            name="morning",
            steps=[
                {"tool_name": "get_system_info", "arguments": {}},
                {"tool_name": "take_screenshot", "arguments": {}},
                {"tool_name": "get_clipboard", "arguments": {}},
            ],
        )

        result = RunAutomation().run(name="morning")
        assert result["ok"] is False
        assert result["steps_run"] == 2
        assert "get_clipboard" not in [c[0] for c in executor.calls]

    def test_run_missing_automation(self, scheduler):
        from ultron.tools.scheduling import RunAutomation

        assert "error" in RunAutomation().run(name="nope")

    def test_delete(self, scheduler):
        from ultron.tools.scheduling import CreateAutomation, DeleteAutomation

        CreateAutomation().run(name="morning", steps=self._steps())
        assert DeleteAutomation().run(name="morning")["deleted"] is True
        assert "error" in DeleteAutomation().run(name="morning")

    def test_automations_persist(self, scheduler, tmp_path):
        from ultron.tools.scheduling import CreateAutomation, TaskScheduler

        CreateAutomation().run(name="morning", steps=self._steps())
        reloaded = TaskScheduler(path=tmp_path / "sched.json", tick_seconds=3600)
        assert reloaded.get_automation("morning") is not None


# ── data / browser tools ─────────────────────────────────────────────
CSV = "name,qty,price\nwidget,3,10.5\ngizmo,12,2.25\nbolt,7,0.5"

HTML = """<html><head><title>My Page</title>
<meta name="description" content="Hello there">
<script>var secret=1;</script></head>
<body><h1>Head</h1><p>Visible text here.</p><a href="/a">Link A</a>
<table><tr><th>Name</th><th>Val</th></tr><tr><td>alpha</td><td>1</td></tr></table>
</body></html>"""

JSON_DOC = json.dumps(
    {
        "results": [{"title": "A", "id": 1}, {"title": "B", "id": 2}],
        "meta": {"total": 2, "tags": ["x", "y"]},
        "1": "numeric key",
    }
)


class TestCsvTools:
    def test_parse_csv_yields_row_objects(self):
        from ultron.tools.data_tools import ParseCsv

        result = ParseCsv().run(text=CSV)
        assert result["headers"] == ["name", "qty", "price"]
        assert result["row_count"] == 3
        assert result["rows"][0] == {"name": "widget", "qty": "3", "price": "10.5"}

    def test_parse_csv_respects_limit(self):
        from ultron.tools.data_tools import ParseCsv

        result = ParseCsv().run(text=CSV, limit=1)
        assert len(result["rows"]) == 1
        assert result["truncated"] is True

    def test_parse_csv_handles_ragged_rows(self):
        from ultron.tools.data_tools import ParseCsv

        result = ParseCsv().run(text="a,b,c\n1,2\n")
        assert result["rows"][0] == {"a": "1", "b": "2", "c": ""}

    def test_parse_csv_errors_on_missing_input(self):
        from ultron.tools.data_tools import ParseCsv

        assert "error" in ParseCsv().run()
        assert "error" in ParseCsv().run(path="/definitely/missing.csv")

    def test_summarize_csv_computes_numeric_stats(self):
        from ultron.tools.data_tools import SummarizeCsv

        stats = SummarizeCsv().run(text=CSV)["columns"]["qty"]
        assert stats["numeric"] is True
        assert stats["min"] == 3.0
        assert stats["max"] == 12.0
        assert stats["mean"] == 7.3333
        assert stats["median"] == 7.0

    def test_summarize_csv_flags_non_numeric_columns(self):
        from ultron.tools.data_tools import SummarizeCsv

        stats = SummarizeCsv().run(text=CSV)["columns"]["name"]
        assert stats["numeric"] is False
        assert stats["distinct"] == 3

    def test_summarize_csv_single_column_and_bad_column(self):
        from ultron.tools.data_tools import SummarizeCsv

        assert "qty" in SummarizeCsv().run(text=CSV, column="qty")["columns"]
        assert "error" in SummarizeCsv().run(text=CSV, column="nope")

    def test_summarize_csv_handles_missing_values(self):
        from ultron.tools.data_tools import SummarizeCsv

        stats = SummarizeCsv().run(text="a,b\n1,\n3,4")["columns"]["b"]
        assert stats["non_empty"] == 1
        assert stats["empty"] == 1
        # Blanks are counted separately but do not disqualify a column: every
        # value that is present is still numeric.
        assert stats["numeric"] is True
        assert stats["min"] == stats["max"] == 4.0


class TestJsonTools:
    def test_parse_json_outlines_structure(self):
        from ultron.tools.data_tools import ParseJson

        outline = ParseJson().run(text=JSON_DOC)["outline"]
        assert outline["results"]["__list_len__"] == 2
        assert outline["meta"]["total"] == "int"

    def test_parse_json_reports_invalid(self):
        from ultron.tools.data_tools import ParseJson

        result = ParseJson().run(text="{not json")
        assert result["valid"] is False
        assert "error" in result

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("results.1.title", "B"),
            ("results[0].title", "A"),
            ("meta.tags", ["x", "y"]),
            ("meta.tags[1]", "y"),
            ("1", "numeric key"),
        ],
    )
    def test_query_json_path_forms(self, path, expected):
        from ultron.tools.data_tools import QueryJson

        assert QueryJson().run(text=JSON_DOC, path=path)["value"] == expected

    def test_query_json_wildcard_flattens(self):
        from ultron.tools.data_tools import QueryJson

        assert QueryJson().run(text=JSON_DOC, path="results[*].id")["value"] == [1, 2]

    def test_query_json_numeric_segment_indexes_a_list(self):
        from ultron.tools.data_tools import QueryJson

        assert QueryJson().run(text=JSON_DOC, path="results.0.id")["value"] == 1

    def test_query_json_numeric_segment_is_a_dict_key_on_a_dict(self):
        """'1' must not be coerced to an index when the container is a dict."""
        from ultron.tools.data_tools import QueryJson

        assert QueryJson().run(text=JSON_DOC, path="1")["value"] == "numeric key"

    @pytest.mark.parametrize(
        "path", ["nope.x", "results.5", "results[*].missing"]
    )
    def test_query_json_bad_paths_error(self, path):
        from ultron.tools.data_tools import QueryJson

        assert "error" in QueryJson().run(text=JSON_DOC, path=path)

    def test_query_json_trailing_wildcard_returns_the_list(self):
        """'results[*]' with nothing after it is just the list, not an error."""
        from ultron.tools.data_tools import QueryJson

        result = QueryJson().run(text=JSON_DOC, path="results[*]")
        assert [item["title"] for item in result["value"]] == ["A", "B"]


class TestHtmlTools:
    def test_parse_html_extracts_text_title_meta_links(self):
        from ultron.tools.data_tools import ParseHtml

        result = ParseHtml().run(text=HTML)
        assert result["title"] == "My Page"
        assert result["meta"]["description"] == "Hello there"
        assert "Visible text here." in result["text"]
        assert result["links"] == [{"href": "/a", "text": "Link A"}]

    def test_parse_html_drops_script_content(self):
        from ultron.tools.data_tools import ParseHtml

        assert "var secret" not in ParseHtml().run(text=HTML)["text"]

    def test_parse_html_can_omit_links(self):
        from ultron.tools.data_tools import ParseHtml

        assert "links" not in ParseHtml().run(text=HTML, include_links=False)

    def test_parse_html_errors_on_empty_input(self):
        from ultron.tools.data_tools import ParseHtml

        assert "error" in ParseHtml().run()

    def test_extract_tables(self):
        from ultron.tools.data_tools import ExtractTables

        result = ExtractTables().run(text=HTML)
        assert result["count"] == 1
        assert result["tables"][0]["rows"] == [["Name", "Val"], ["alpha", "1"]]

    def test_extract_tables_index_selection(self):
        from ultron.tools.data_tools import ExtractTables

        assert ExtractTables().run(text=HTML, index=0)["count"] == 1
        assert "error" in ExtractTables().run(text=HTML, index=9)


class TestNetworkTools:
    def test_fetch_requires_a_url(self):
        from ultron.tools.data_tools import FetchWebpage

        assert "error" in FetchWebpage().run()

    def test_fetch_blocks_private_and_non_http_urls(self):
        from ultron.tools.data_tools import FetchWebpage

        for url in ("file:///C:/Windows/win.ini", "ftp://example.com/x", ""):
            assert "error" in FetchWebpage().run(url=url)

    def test_download_requires_a_url(self):
        from ultron.tools.data_tools import DownloadFile

        assert "error" in DownloadFile().run()


# ── registration invariants for the new modules ──────────────────────
def test_new_tools_declare_risk_and_reachable_phrases():
    catalog = default_catalog()
    new_names = [
        n for n, m in catalog.metadata.items() if m.category in ("windows", "scheduling", "data")
    ]
    assert len(new_names) >= 20, f"expected the new tools to be registered, got {new_names}"
    for name in new_names:
        assert catalog.risk_of(name) is not None
        probe = "please " + name.replace("_", " ") + " now"
        assert catalog.best_phrase_match(probe) is not None, f"{name} is unreachable"


def test_parsers_are_read_only():
    """Parsing must not be classified as mutating."""
    catalog = default_catalog()
    for name, meta in catalog.metadata.items():
        if meta.category == "data":
            assert not meta.mutates, f"{name} is a parser and must not mutate"
