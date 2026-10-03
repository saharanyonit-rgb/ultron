"""Deferred task scheduling and reusable automations.

Scheduling a tool means running it later with nobody watching, so the
permission gate cannot ask the user anything at fire time. Two rules follow
from that, and both are enforced here rather than left to callers:

1. Only tools at HIGH or below may be deferred. `execute_command` and
   `system_shutdown` are CRITICAL and are refused unless `allow_critical` is
   passed explicitly, because a typo'd argument would otherwise execute
   unattended.
2. Deferred work still goes through the same `ToolExecutor` as interactive
   work, so it keeps the configured gate and audit trail. This is why the
   executor is injectable (`set_executor`) instead of the tools constructing
   their own — a self-built executor would silently drop the user's gate.

Automations are named, reusable step lists; `run_automation` executes one
immediately through the same executor.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ultron.risk import RiskLevel
from ultron.tools.base import Tool
from ultron.tools.catalog import default_catalog

logger = logging.getLogger("ultron.tools.scheduling")

DEFAULT_TICK_SECONDS = 5.0
_MAX_CANCELLED_RETAINED = 200

# Ordinal -> RiskLevel ordering helper (RiskLevel is a StrEnum, not ordered).
_RISK_ORDER = {
    RiskLevel.READ: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

_REL_RE = re.compile(
    r"^\s*(?:in\s+)?(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|"
    r"h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.I,
)
_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
}


def _state_path() -> Path:
    override = os.environ.get("ULTRON_SCHEDULE_FILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".ultron" / "schedules.json"


def parse_when(value: str) -> datetime:
    """Parse a due time into an aware datetime.

    Accepts an ISO timestamp, a bare ``HH:MM`` (today, or tomorrow if that has
    already passed), or a relative offset such as ``30m`` / ``in 2 hours``.

    Raises:
        ValueError: if the value cannot be interpreted.
    """
    raw = str(value).strip()
    if not raw:
        raise ValueError("empty time value")

    # Relative offset.
    match = _REL_RE.match(raw)
    if match:
        amount = float(match.group(1))
        unit = match.group(2).lower()
        return datetime.now().astimezone() + timedelta(seconds=amount * _UNIT_SECONDS[unit])

    # Bare clock time.
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", raw):
        parts = [int(p) for p in raw.split(":")]
        while len(parts) < 3:
            parts.append(0)
        now = datetime.now().astimezone()
        candidate = now.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    # ISO timestamp (with or without offset).
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"could not parse time {value!r}; use ISO (2026-01-05T09:30), "
            f"HH:MM, or a relative offset like 30m / 2h / 1d"
        ) from exc
    return parsed if parsed.tzinfo else parsed.astimezone()


@dataclass
class ScheduledTask:
    """One deferred tool call."""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    run_at: str  # ISO 8601
    risk: str
    created_at: str
    status: str = "pending"  # pending | completed | failed | cancelled
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScheduledTask:
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            tool_name=str(data.get("tool_name", "")),
            arguments=dict(data.get("arguments") or {}),
            run_at=str(data.get("run_at", "")),
            risk=str(data.get("risk", RiskLevel.MEDIUM.value)),
            created_at=str(data.get("created_at", "")),
            status=str(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class Automation:
    """A named, reusable list of tool calls."""

    name: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Automation:
        return cls(
            name=str(data.get("name", "")),
            steps=list(data.get("steps") or []),
            description=str(data.get("description", "")),
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            created_at=str(data.get("created_at") or datetime.now().astimezone().isoformat()),
        )


class TaskScheduler:
    """Background scheduler for deferred tool calls and stored automations.

    State is persisted to JSON so a restart does not silently drop pending work.
    A single daemon thread ticks; execution failures are recorded on the task
    rather than raised, because there is no caller to receive them.
    """

    def __init__(self, path: Path | None = None, tick_seconds: float = DEFAULT_TICK_SECONDS) -> None:
        self._path = path
        self._tick = tick_seconds
        self._lock = threading.RLock()
        self._tasks: dict[str, ScheduledTask] = {}
        self._automations: dict[str, Automation] = {}
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._executor: Any = None
        self._load()

    # ── persistence ─────────────────────────────────────────────
    @property
    def path(self) -> Path:
        return self._path if self._path is not None else _state_path()

    def _load(self) -> None:
        target = self.path
        if not target.is_file():
            return
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not read scheduler state %s: %s", target, exc)
            return
        with self._lock:
            self._tasks = {
                str(t.get("id")): ScheduledTask.from_dict(t)
                for t in data.get("tasks", [])
                if isinstance(t, dict)
            }
            # Anything mid-flight when we exited is retried on next tick; it was
            # never confirmed complete.
            self._automations = {
                str(a.get("id")): Automation.from_dict(a)
                for a in data.get("automations", [])
                if isinstance(a, dict)
            }

    def _save(self) -> None:
        target = self.path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                payload = {
                    "tasks": [t.to_dict() for t in self._tasks.values()],
                    "automations": [a.to_dict() for a in self._automations.values()],
                }
            target.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except OSError as exc:
            logger.warning("could not persist scheduler state: %s", exc)

    # ── executor wiring ─────────────────────────────────────────
    def set_executor(self, executor: Any) -> None:
        """Use `executor` for deferred runs so the user's gate applies."""
        self._executor = executor

    def _get_executor(self) -> Any:
        if self._executor is not None:
            return self._executor
        # Lazy default keeps this module importable on its own; the process
        # entrypoints call set_executor() with the gated, audited executor.
        from ultron.tools import ToolExecutor, ToolRegistry

        logger.debug("scheduler executor not configured; using a default executor")
        self._executor = ToolExecutor(ToolRegistry())
        return self._executor

    # ── tasks ───────────────────────────────────────────────────
    def schedule(self, task: ScheduledTask) -> ScheduledTask:
        with self._lock:
            self._tasks[task.id] = task
        self._save()
        self.ensure_running()
        return task

    def due_tasks(self, now: datetime | None = None) -> list[ScheduledTask]:
        moment = now or datetime.now().astimezone()
        due: list[ScheduledTask] = []
        with self._lock:
            for task in self._tasks.values():
                if task.status != "pending":
                    continue
                try:
                    run_at = datetime.fromisoformat(task.run_at)
                except ValueError:
                    continue
                if run_at.tzinfo is None:
                    run_at = run_at.astimezone()
                if run_at <= moment:
                    due.append(task)
        return due

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status != "pending":
                return False
            task.status = "cancelled"
        self._prune()
        self._save()
        return True

    def _prune(self) -> None:
        """Bound the state file: keep all pending, trim settled history."""
        with self._lock:
            settled = [t for t in self._tasks.values() if t.status != "pending"]
            if len(settled) > _MAX_CANCELLED_RETAINED:
                settled.sort(key=lambda t: t.run_at)
                drop = {t.id for t in settled[: len(settled) - _MAX_CANCELLED_RETAINED]}
                for key in drop:
                    self._tasks.pop(key, None)

    def list_tasks(self, include_settled: bool = True) -> list[ScheduledTask]:
        with self._lock:
            tasks = list(self._tasks.values())
        if not include_settled:
            tasks = [t for t in tasks if t.status == "pending"]
        return sorted(tasks, key=lambda t: t.run_at)

    def run_due(self) -> int:
        """Execute every due task once. Returns the number run."""
        count = 0
        for task in self.due_tasks():
            with self._lock:
                current = self._tasks.get(task.id)
                if current is None or current.status != "pending":
                    continue  # already claimed
                current.status = "running"
            try:
                result = self._get_executor().execute(task.tool_name, task.arguments)
                with self._lock:
                    current.status = (
                        "completed"
                        if getattr(result, "allowed", False) and not getattr(result, "error", None)
                        else "failed"
                    )
                    current.result = dict(getattr(result, "output", {}) or {})
                    current.error = getattr(result, "error", None)
            except Exception as exc:  # noqa: BLE001 - no caller to raise to
                logger.exception("scheduled task %s failed", task.id)
                with self._lock:
                    current.status = "failed"
                    current.error = f"{type(exc).__name__}: {exc}"
            self._save()
            count += 1
        return count

    def _loop(self) -> None:
        while not self._stop.wait(self._tick):
            try:
                self.run_due()
            except Exception:  # noqa: BLE001 - the thread must survive
                logger.exception("scheduler tick failed")

    def ensure_running(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop, name="ultron-scheduler", daemon=True
            )
            self._thread.start()
            logger.info("scheduler started (tick=%.1fs)", self._tick)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._tick + 1)
        self._thread = None

    # ── automations ─────────────────────────────────────────────
    def put_automation(self, automation: Automation, overwrite: bool = False) -> Automation | None:
        with self._lock:
            # Snapshot the ids first: replacing an entry pops from the dict we
            # would otherwise be iterating, which raises at runtime.
            clash = next(
                (
                    key
                    for key, existing in list(self._automations.items())
                    if existing.name.lower() == automation.name.lower()
                ),
                None,
            )
            if clash is not None:
                if not overwrite:
                    return None
                automation.id = self._automations[clash].id
                del self._automations[clash]
            self._automations[automation.id] = automation
        self._save()
        return automation

    def get_automation(self, name: str) -> Automation | None:
        with self._lock:
            for automation in self._automations.values():
                if automation.name.lower() == str(name).strip().lower():
                    return automation
        return None

    def delete_automation(self, name: str) -> bool:
        with self._lock:
            # Collect first, then mutate, to avoid changing dict size mid-iteration.
            key = next(
                (
                    k
                    for k, existing in list(self._automations.items())
                    if existing.name.lower() == str(name).strip().lower()
                ),
                None,
            )
            if key is None:
                return False
            del self._automations[key]
            self._save()
            return True

    def list_automations(self) -> list[Automation]:
        with self._lock:
            return sorted(self._automations.values(), key=lambda a: a.name.lower())

    def run_automation(self, automation: Automation) -> dict[str, Any]:
        """Execute every step in order, stopping at the first hard failure."""
        steps: list[dict[str, Any]] = []
        executor = self._get_executor()
        for index, step in enumerate(automation.steps, start=1):
            tool_name = str(step.get("tool_name") or step.get("tool") or "")
            arguments = dict(step.get("arguments") or {})
            if not tool_name:
                steps.append({"index": index, "tool_name": "", "status": "failed",
                              "error": "step has no tool_name"})
                break
            try:
                result = executor.execute(tool_name, arguments)
                steps.append(
                    {
                        "index": index,
                        "tool_name": tool_name,
                        "status": "completed"
                        if getattr(result, "allowed", False) and not getattr(result, "error", None)
                        else "failed",
                        "allowed": bool(getattr(result, "allowed", False)),
                        "output": dict(getattr(result, "output", {}) or {}),
                        "error": getattr(result, "error", None),
                    }
                )
                if steps[-1]["status"] == "failed":
                    break
            except Exception as exc:  # noqa: BLE001
                logger.exception("automation %s step %d failed", automation.name, index)
                steps.append({"index": index, "tool_name": tool_name, "status": "failed",
                              "error": f"{type(exc).__name__}: {exc}"})
                break
        return {
            "automation": automation.name,
            "steps_run": len(steps),
            "steps_total": len(automation.steps),
            "ok": all(s["status"] == "completed" for s in steps) and bool(steps),
            "steps": steps,
        }


_SCHEDULER: TaskScheduler | None = None
_SCHED_LOCK = threading.Lock()


def get_scheduler() -> TaskScheduler:
    """Process-wide scheduler singleton."""
    global _SCHEDULER
    with _SCHED_LOCK:
        if _SCHEDULER is None:
            _SCHEDULER = TaskScheduler()
        return _SCHEDULER


def set_executor(executor: Any) -> None:
    """Point deferred work at the process's gated, audited executor."""
    get_scheduler().set_executor(executor)


class ScheduleTool(Tool):
    name = "schedule_tool"
    risk = RiskLevel.HIGH
    mutates = True
    category = "scheduling"
    keywords = (
        "schedule a tool",
        "run this later",
        "run at a time",
        "schedule task",
        "remind me to run",
        "do this in",
        "later run",
        "defer this",
    )
    description = (
        "Schedule a tool call to run later. Accepts an ISO timestamp "
        "(2026-01-05T09:30), a clock time (09:30), or a relative offset "
        "(30m, 2h, 1d). The call runs unattended, so CRITICAL tools such as "
        "execute_command are refused unless allow_critical is set."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string", "description": "Registered tool to call later."},
            "arguments": {
                "type": "object",
                "description": "Arguments for the tool.",
                "additionalProperties": True,
            },
            "when": {
                "type": "string",
                "description": "ISO timestamp, HH:MM, or offset like 30m / 2h / 1d.",
            },
            "allow_critical": {
                "type": "boolean",
                "description": "Permit deferring CRITICAL tools. Defaults to false.",
            },
        },
        "required": ["tool_name", "when"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "tool_name": {"type": "string"},
            "run_at": {"type": "string"},
            "risk": {"type": "string"},
        },
    }

    def run(
        self,
        tool_name: str = "",
        when: str = "",
        arguments: dict[str, Any] | None = None,
        allow_critical: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        catalog = default_catalog()
        tool = catalog.get(str(tool_name))
        if tool is None:
            return {
                "error": f"unknown tool {tool_name!r}",
                "hint": "the tool must be registered; see /api/tools for the list",
            }
        try:
            run_at = parse_when(when)
        except ValueError as exc:
            return {"error": str(exc)}

        risk = tool.effective_risk
        if _RISK_ORDER[risk] >= _RISK_ORDER[RiskLevel.CRITICAL] and not allow_critical:
            return {
                "error": (
                    f"refusing to defer {tool.name!r}: it is CRITICAL and will run "
                    f"with nobody able to confirm it. Set allow_critical=true if "
                    f"this is intended."
                ),
                "risk": risk.value,
            }

        task = ScheduledTask(
            id=uuid.uuid4().hex[:12],
            tool_name=tool.name,
            arguments=dict(arguments or {}),
            run_at=run_at.isoformat(),
            risk=risk.value,
            created_at=datetime.now().astimezone().isoformat(),
        )
        get_scheduler().schedule(task)
        return {
            "id": task.id,
            "tool_name": task.tool_name,
            "run_at": task.run_at,
            "risk": task.risk,
            "status": task.status,
        }


class ListScheduledTasks(Tool):
    name = "list_scheduled_tasks"
    risk = RiskLevel.READ
    category = "scheduling"
    keywords = (
        "list scheduled tasks",
        "scheduled tasks",
        "what is scheduled",
        "pending tasks",
        "my schedule",
        "upcoming tasks",
    )
    description = "List deferred tool calls, newest due time last."
    parameters = {
        "type": "object",
        "properties": {
            "include_settled": {
                "type": "boolean",
                "description": "Include completed/failed/cancelled. Default true.",
            }
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}, "tasks": {"type": "array"}},
    }

    def run(self, include_settled: bool = True, **_: Any) -> dict[str, Any]:
        tasks = get_scheduler().list_tasks(include_settled=include_settled)
        return {"count": len(tasks), "tasks": [t.to_dict() for t in tasks]}


class CancelScheduledTask(Tool):
    name = "cancel_scheduled_task"
    risk = RiskLevel.LOW
    mutates = True
    category = "scheduling"
    keywords = (
        "cancel scheduled task",
        "unschedule",
        "delete scheduled task",
        "cancel job",
        "stop scheduled",
    )
    description = "Cancel a pending scheduled task by its id."
    parameters = {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Task id to cancel."}},
        "required": ["id"],
    }
    output_schema = {"type": "object", "properties": {"cancelled": {"type": "boolean"}}}

    def run(self, id: str = "", **_: Any) -> dict[str, Any]:
        if not get_scheduler().cancel(str(id).strip()):
            return {"error": f"no pending task with id {id!r}"}
        return {"cancelled": True, "id": str(id)}


class CreateAutomation(Tool):
    name = "create_automation"
    risk = RiskLevel.MEDIUM
    mutates = True
    category = "scheduling"
    keywords = (
        "create automation",
        "save automation",
        "make a routine",
        "record a workflow",
        "create routine",
        "save this workflow",
    )
    description = (
        "Store a named, reusable list of tool calls (steps). Each step is "
        "{'tool_name': ..., 'arguments': {...}}. Later run it with "
        "run_automation, optionally on a schedule."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Unique routine name."},
            "steps": {
                "type": "array",
                "description": "Ordered tool calls.",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "arguments": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["tool_name"],
                },
            },
            "description": {"type": "string"},
            "overwrite": {
                "type": "boolean",
                "description": "Replace an existing routine with the same name.",
            },
        },
        "required": ["name", "steps"],
    }
    output_schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}, "name": {"type": "string"},
                       "steps": {"type": "integer"}},
    }

    def run(
        self,
        name: str = "",
        steps: list[dict[str, Any]] | None = None,
        description: str = "",
        overwrite: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        label = str(name).strip()
        if not label:
            return {"error": "name is required"}
        if not isinstance(steps, list) or not steps:
            return {"error": "steps must be a non-empty array of tool calls"}

        catalog = default_catalog()
        unknown = [
            str(s.get("tool_name") or "")
            for s in steps
            if isinstance(s, dict) and catalog.get(str(s.get("tool_name") or "")) is None
        ]
        if unknown:
            return {"error": f"unknown tool(s) in steps: {sorted(set(unknown))}"}

        automation = Automation(name=label, steps=list(steps), description=description)
        stored = get_scheduler().put_automation(automation, overwrite=overwrite)
        if stored is None:
            return {"error": f"automation {label!r} already exists", "hint": "pass overwrite=true"}
        return {"id": stored.id, "name": stored.name, "steps": len(stored.steps)}


class ListAutomations(Tool):
    name = "list_automations"
    risk = RiskLevel.READ
    category = "scheduling"
    keywords = (
        "list automations",
        "my routines",
        "saved workflows",
        "show automations",
        "list routines",
    )
    description = "List stored automations with their step counts."
    parameters = {"type": "object", "properties": {}, "required": []}
    output_schema = {
        "type": "object",
        "properties": {"count": {"type": "integer"}, "automations": {"type": "array"}},
    }

    def run(self, **_: Any) -> dict[str, Any]:
        found = get_scheduler().list_automations()
        return {
            "count": len(found),
            "automations": [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "steps": len(a.steps),
                }
                for a in found
            ],
        }


class DeleteAutomation(Tool):
    name = "delete_automation"
    risk = RiskLevel.MEDIUM
    mutates = True
    category = "scheduling"
    keywords = (
        "delete automation",
        "remove routine",
        "delete routine",
        "remove workflow",
    )
    description = "Delete a stored automation by name."
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Routine name."}},
        "required": ["name"],
    }
    output_schema = {"type": "object", "properties": {"deleted": {"type": "boolean"}}}

    def run(self, name: str = "", **_: Any) -> dict[str, Any]:
        if not get_scheduler().delete_automation(str(name)):
            return {"error": f"no automation named {name!r}"}
        return {"deleted": True, "name": str(name)}


class RunAutomation(Tool):
    name = "run_automation"
    risk = RiskLevel.HIGH
    mutates = True
    category = "scheduling"
    keywords = (
        "run automation",
        "run routine",
        "run my routine",
        "execute workflow",
        "run workflow",
        "run saved automation",
    )
    description = (
        "Run a stored automation now, in step order, stopping at the first "
        "failure. Each step goes through the normal permission gate."
    )
    parameters = {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Routine name."}},
        "required": ["name"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "automation": {"type": "string"},
            "ok": {"type": "boolean"},
            "steps": {"type": "array"},
        },
    }

    def run(self, name: str = "", **_: Any) -> dict[str, Any]:
        automation = get_scheduler().get_automation(str(name))
        if automation is None:
            return {"error": f"no automation named {name!r}"}
        return get_scheduler().run_automation(automation)


__all__ = [
    "Automation",
    "CancelScheduledTask",
    "CreateAutomation",
    "DeleteAutomation",
    "ListAutomations",
    "ListScheduledTasks",
    "RunAutomation",
    "ScheduleTool",
    "ScheduledTask",
    "TaskScheduler",
    "get_scheduler",
    "parse_when",
    "set_executor",
]
