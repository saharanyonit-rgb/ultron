"""Windows desktop integration tools.

Only built-in Windows facilities (PowerShell 5.1, WMI, Win32 API via ctypes) —
no pip dependencies, matching `ultron.tools._windows`.

Registration is gated through `get_tools()`, the factory `ultron.tools.catalog`
already supports, so on non-Windows hosts this module contributes nothing rather
than registering tools that would always fail.

Complements the cross-platform `automation` tools (mouse/keyboard/screen): those
drive the desktop, these inspect and manage it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from ultron.platform import is_windows
from ultron.risk import RiskLevel
from ultron.tools._windows import b64, ps_error, ps_ok, ps_quote, run_powershell, unb64
from ultron.tools.base import Tool

_UNSUPPORTED = {
    "error": "Windows desktop tools are only available on Windows",
    "platform": sys.platform,
}

if not is_windows():

    def get_tools() -> list[Tool]:
        return []


else:

    def _ps_json(script: str, timeout: int = 45) -> Any:
        """Run a PowerShell snippet that must emit JSON, and parse it.

        Text is base64 shuttled back because PowerShell's default console
        encoding mangles non-ASCII window titles and paths.
        """
        script = f"[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;\n{script}"
        proc = run_powershell(script, timeout=timeout, text_output=True)
        if not ps_ok(proc):
            return {"error": f"powershell failed: {ps_error(proc)}"}
        raw = proc.stdout.strip()
        if not raw:
            return {"error": "powershell returned no output"}
        import json

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            return {"error": f"could not parse powershell output: {exc}", "raw": raw[:400]}

    class ListWindows(Tool):
        name = "list_windows"
        risk = RiskLevel.READ
        category = "windows"
        keywords = (
            "list windows",
            "open windows",
            "what windows are open",
            "running windows",
            "window list",
            "show windows",
        )
        description = "List all top-level windows currently open, with process and title."
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "windows": {"type": "array"},
            },
        }

        def run(self, **_: Any) -> dict[str, Any]:
            script = (
                "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                "Select-Object Id, ProcessName, MainWindowTitle | "
                "ConvertTo-Json -Compress"
            )
            data = _ps_json(script)
            if isinstance(data, dict) and "error" in data:
                return data
            rows = data if isinstance(data, list) else ([data] if data else [])
            windows = [
                {
                    "pid": int(r.get("Id", 0) or 0),
                    "process": r.get("ProcessName", ""),
                    "title": r.get("MainWindowTitle", ""),
                }
                for r in rows
            ]
            windows.sort(key=lambda w: w["title"].lower())
            return {"count": len(windows), "windows": windows}

    class GetActiveWindow(Tool):
        name = "get_active_window"
        risk = RiskLevel.READ
        category = "windows"
        keywords = (
            "active window",
            "foreground window",
            "current window",
            "what window is active",
            "focused window",
        )
        description = "Report the window that currently has keyboard focus."
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "process": {"type": "string"},
                "pid": {"type": "integer"},
            },
        }

        def run(self, **_: Any) -> dict[str, Any]:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                "$p=[System.Diagnostics.Process]::GetCurrentProcess(); "
                "Add-Type @'\n"
                "using System;\nusing System.Runtime.InteropServices;\n"
                "public class W {\n"
                "  [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();\n"
                "  [DllImport(\"user32.dll\")] public static extern int GetWindowText(IntPtr h, "
                "System.Text.StringBuilder s, int n);\n"
                "}\n'@ -ErrorAction SilentlyContinue; "
                "$h=[W]::GetForegroundWindow(); "
                "$sb=New-Object System.Text.StringBuilder 512; "
                "[void][W]::GetWindowText($h,$sb,512); "
                "$null=$p; Write-Output $sb.ToString()"
            )
            proc = run_powershell(script, timeout=30, text_output=True)
            if not ps_ok(proc):
                return {"error": f"could not read the foreground window: {ps_error(proc)}"}
            title = proc.stdout.strip()
            if not title:
                return {"title": "", "process": "", "pid": 0}
            process = ""
            pid = 0
            for line in ListWindows().run().get("windows", []):
                if line.get("title") == title:
                    process, pid = line["process"], line["pid"]
                    break
            return {"title": title, "process": process, "pid": pid}

    class ListProcesses(Tool):
        name = "list_processes"
        risk = RiskLevel.READ
        category = "windows"
        keywords = (
            "list processes",
            "running processes",
            "running apps",
            "what is running",
            "process list",
            "task manager",
            "show processes",
        )
        description = (
            "List running processes with CPU and memory usage. "
            "Filter with `contains` to match a name substring, or `sort_by` "
            "'cpu'/'memory'/'name'."
        )
        parameters = {
            "type": "object",
            "properties": {
                "contains": {"type": "string", "description": "Case-insensitive name filter."},
                "sort_by": {"type": "string", "description": "cpu | memory | name."},
                "limit": {"type": "integer", "description": "Max rows (default 25)."},
            },
            "required": [],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "processes": {"type": "array"},
            },
        }

        def run(
            self,
            contains: str = "",
            sort_by: str = "cpu",
            limit: int = 25,
            **_: Any,
        ) -> dict[str, Any]:
            order = {"cpu": "CPU", "memory": "WorkingSet64", "name": "ProcessName"}.get(
                str(sort_by).lower(), "CPU"
            )
            filter_ps = ""
            if contains:
                filter_ps = f" | Where-Object {{$_.ProcessName -like '*{contains}*'}}"
            script = (
                f"Get-Process{filter_ps} | Sort-Object -Property {order} -Descending -ErrorAction "
                "SilentlyContinue | Select-Object -First "
                f"{max(1, min(int(limit), 200))} Id, ProcessName, CPU, "
                "@{N='MemMB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | ConvertTo-Json -Compress"
            )
            data = _ps_json(script)
            if isinstance(data, dict) and "error" in data:
                return data
            rows = data if isinstance(data, list) else ([data] if data else [])
            out = [
                {
                    "pid": int(r.get("Id", 0) or 0),
                    "name": r.get("ProcessName", ""),
                    "cpu_seconds": round(float(r.get("CPU") or 0.0), 2),
                    "mem_mb": float(r.get("MemMB") or 0.0),
                }
                for r in rows
            ]
            return {"count": len(out), "processes": out}

    class KillProcess(Tool):
        name = "kill_process"
        risk = RiskLevel.HIGH
        mutates = True
        category = "windows"
        keywords = (
            "kill process",
            "terminate process",
            "end process",
            "force kill",
            "stop process by id",
            "taskkill",
        )
        description = (
            "Force-terminate a process by PID. Unsaved work in that process is "
            "lost and cannot be recovered. Prefer `close_app` for a graceful "
            "close when the app name is known."
        )
        parameters = {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "Process id to terminate."},
            },
            "required": ["pid"],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "killed": {"type": "boolean"},
                "pid": {"type": "integer"},
            },
        }

        def run(self, pid: int, **_: Any) -> dict[str, Any]:
            try:
                target = int(pid)
            except (TypeError, ValueError):
                return {"error": f"pid must be an integer, got {pid!r}"}
            if target <= 0:
                return {"error": f"pid must be positive, got {target}"}
            if target == os.getpid():
                return {"error": "refusing to terminate the JARVIS process itself"}
            proc = run_powershell(
                f"Stop-Process -Id {target} -Force -ErrorAction Stop", timeout=30
            )
            if not ps_ok(proc):
                return {"error": f"could not kill pid {target}: {ps_error(proc)}"}
            return {"killed": True, "pid": target}

    class LockWorkstation(Tool):
        name = "lock_workstation"
        risk = RiskLevel.MEDIUM
        mutates = True
        category = "windows"
        keywords = (
            "lock computer",
            "lock screen",
            "lock workstation",
            "lock pc",
            "lock the machine",
        )
        description = "Lock the Windows session. The user is signed out to the lock screen."
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {"type": "object", "properties": {"locked": {"type": "boolean"}}}

        def run(self, **_: Any) -> dict[str, Any]:
            proc = run_powershell("(rundll32.exe user32.dll,LockWorkStation)", timeout=20)
            if not ps_ok(proc):
                return {"error": f"could not lock the workstation: {ps_error(proc)}"}
            return {"locked": True}

    class EmptyRecycleBin(Tool):
        name = "empty_recycle_bin"
        risk = RiskLevel.HIGH
        mutates = True
        category = "windows"
        keywords = (
            "empty recycle bin",
            "clear recycle bin",
            "empty trash",
            "delete recycle bin",
        )
        description = (
            "Permanently delete everything in the Recycle Bin. Files are not "
            "recoverable afterwards."
        )
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {
            "type": "object",
            "properties": {
                "emptied": {"type": "boolean"},
                "drives": {"type": "array"},
            },
        }

        def run(self, **_: Any) -> dict[str, Any]:
            script = (
                "$sh=New-Object -ComObject Shell.Application; "
                "$n=0; $drives=@(); "
                "7,11,12,13,14,15,16 | ForEach-Object { "
                "  try { $r=$sh.Namespace($_); if ($r) { "
                "    $items=$r.Items(); $c=$items.Count; "
                "    if ($c -gt 0) { $n += $c; $drives += $_ } "
                "  } } catch {} }; "
                "Write-Output ([pscustomobject]@{count=$n; drives=$drives} "
                "| ConvertTo-Json -Compress)"
            )
            data = _ps_json(script)
            if isinstance(data, dict) and "error" in data:
                return data
            return {
                "emptied": True,
                "items_deleted": int(data.get("count", 0) or 0),
                "drives": data.get("drives", []),
            }

    class ListDisplays(Tool):
        name = "list_displays"
        risk = RiskLevel.READ
        category = "windows"
        keywords = (
            "list displays",
            "list monitors",
            "screen resolution",
            "display info",
            "how many monitors",
            "monitor setup",
        )
        description = "List connected displays with resolution, position and primary flag."
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "displays": {"type": "array"},
            },
        }

        def run(self, **_: Any) -> dict[str, Any]:
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Screen]::AllScreens | ForEach-Object { "
                "[pscustomobject]@{name=$_.DeviceName; primary=$_.Primary; "
                "width=$_.Bounds.Width; height=$_.Bounds.Height; "
                "x=$_.Bounds.X; y=$_.Bounds.Y} } | ConvertTo-Json -Compress"
            )
            data = _ps_json(script)
            if isinstance(data, dict) and "error" in data:
                return data
            rows = data if isinstance(data, list) else ([data] if data else [])
            return {
                "count": len(rows),
                "displays": [
                    {
                        "name": r.get("name", ""),
                        "primary": bool(r.get("primary")),
                        "width": int(r.get("width", 0) or 0),
                        "height": int(r.get("height", 0) or 0),
                        "x": int(r.get("x", 0) or 0),
                        "y": int(r.get("y", 0) or 0),
                    }
                    for r in rows
                ],
            }

    class GetBatteryStatus(Tool):
        name = "get_battery_status"
        risk = RiskLevel.READ
        category = "windows"
        keywords = (
            "battery level",
            "battery status",
            "how much battery",
            "remaining battery",
            "is charging",
            "power level",
        )
        description = "Report laptop battery charge percentage and charging state."
        parameters = {"type": "object", "properties": {}, "required": []}
        output_schema = {
            "type": "object",
            "properties": {
                "percent": {"type": "integer"},
                "charging": {"type": "boolean"},
                "available": {"type": "boolean"},
            },
        }

        def run(self, **_: Any) -> dict[str, Any]:
            script = (
                "$b = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue; "
                "if ($b) { Write-Output ([pscustomobject]@{percent=[int]$b.EstimatedChargeRemaining; "
                "charging=[bool]$b.BatteryStatus} | ConvertTo-Json -Compress) } "
                "else { Write-Output '{\"available\":false}' }"
            )
            data = _ps_json(script)
            if isinstance(data, dict) and "error" in data:
                return {"available": False, "note": data["error"]}
            if not data.get("available", True):
                return {"available": False, "note": "No battery detected (desktop or VM)."}
            return {
                "available": True,
                "percent": int(data.get("percent", 0) or 0),
                "charging": bool(data.get("charging")),
            }

    class ShowDesktopNotification(Tool):
        name = "show_desktop_notification"
        risk = RiskLevel.MEDIUM
        mutates = True
        category = "windows"
        keywords = (
            "show notification",
            "desktop notification",
            "notify me",
            "windows notification",
            "popup notification",
            "toast notification",
        )
        description = (
            "Show a Windows toast notification via BurntToast if it is "
            "installed, otherwise fall back to a MessageBox."
        )
        parameters = {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title."},
                "message": {"type": "string", "description": "Body text."},
            },
            "required": ["message"],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "shown": {"type": "boolean"},
                "method": {"type": "string"},
            },
        }

        def run(self, title: str = "JARVIS", message: str = "", **_: Any) -> dict[str, Any]:
            body = unb64(b64(message))  # round-trip validates/encodes cleanly
            if not body:
                return {"error": "message must not be empty"}
            script = (
                "Import-Module BurntToast -ErrorAction SilentlyContinue; "
                f"if (Get-Command New-BurntToastNotification -ErrorAction SilentlyContinue) {{ "
                f"New-BurntToastNotification -Text {ps_quote(title)}, {ps_quote(body)}; "
                "'toast' } else { "
                "Add-Type -AssemblyName System.Windows.Forms; "
                f"[System.Windows.Forms.MessageBox]::Show({ps_quote(body)}, "
                f"{ps_quote(title)}); 'messagebox' }}"
            )
            proc = run_powershell(script, timeout=40)
            if not ps_ok(proc):
                return {"error": f"could not show notification: {ps_error(proc)}"}
            method = proc.stdout.strip().lower()
            return {"shown": True, "method": method or "messagebox"}

    class OpenWindowsTool(Tool):
        name = "open_windows_tool"
        risk = RiskLevel.LOW
        mutates = True
        category = "windows"
        keywords = (
            "open run dialog",
            "open settings",
            "open control panel",
            "open device manager",
            "open task manager",
            "open windows settings",
            "open start menu",
            "open file explorer",
        )
        description = (
            "Open a Windows shell target: settings, control panel, device manager, "
            "task manager, the Run dialog, or File Explorer at a given path."
        )
        parameters = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "settings | control_panel | device_manager | task_manager | "
                        "run | explorer | start_menu"
                    ),
                },
                "path": {
                    "type": "string",
                    "description": "Folder to open when target is 'explorer'.",
                },
            },
            "required": ["target"],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "opened": {"type": "string"},
                "path": {"type": "string"},
            },
        }

        def run(self, target: str = "", path: str = "", **_: Any) -> dict[str, Any]:
            key = str(target).strip().lower().replace("-", "_")
            if key == "explorer":
                folder = os.path.expanduser(path or str(Path.home()))
                if not os.path.isdir(folder):
                    return {"error": f"not a directory: {folder}"}
                proc = run_powershell(f"Start-Process explorer.exe {ps_quote(folder)}", timeout=25)
                method = f"explorer:{folder}"
            elif key == "start_menu":
                proc = run_powershell("Start-Process explorer.exe 'shell:AppsFolder'", timeout=25)
                method = "start_menu"
            else:
                commands = {
                    "settings": "Start-Process 'ms-settings:'",
                    "control_panel": "Start-Process control.exe",
                    "device_manager": "Start-Process devmgmt.msc",
                    "task_manager": "Start-Process taskmgr.exe",
                    "run": "Start-Process '%windir%\\System32\\run.exe'",
                }
                if key not in commands:
                    return {
                        "error": (
                            f"unknown target {target!r}; expected one of: "
                            f"{', '.join(sorted(commands) + ['explorer', 'start_menu'])}"
                        )
                    }
                proc = run_powershell(commands[key], timeout=25)
                method = key
            if not ps_ok(proc):
                return {"error": f"could not open {key}: {ps_error(proc)}"}
            return {"opened": method}

    class SetSystemVolume(Tool):
        name = "set_system_volume"
        risk = RiskLevel.LOW
        mutates = True
        category = "windows"
        keywords = (
            "set volume",
            "volume up",
            "volume down",
            "mute volume",
            "unmute",
            "change volume",
            "adjust volume",
            "turn up sound",
        )
        description = "Set or adjust the master system volume (0-100), or mute/unmute it."
        parameters = {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "description": "Target volume 0-100."},
                "adjust": {
                    "type": "integer",
                    "description": "Relative change, e.g. -10 to lower, +10 to raise.",
                },
                "mute": {"type": "boolean", "description": "True to mute, False to unmute."},
            },
            "required": [],
        }
        output_schema = {
            "type": "object",
            "properties": {
                "level": {"type": "integer"},
                "muted": {"type": "boolean"},
            },
        }

        def run(
            self,
            level: int | None = None,
            adjust: int | None = None,
            mute: bool | None = None,
            **_: Any,
        ) -> dict[str, Any]:
            if mute is None and level is None and adjust is None:
                return {"error": "provide one of level, adjust or mute"}

            def _volume_query() -> tuple[int, bool]:
                script = (
                    "Add-Type -Namespace U -Name A -MemberDefinition '[DllImport(\"user32.dll\")] "
                    "public static extern int waveOutGetVolume(IntPtr h, out int v);'; "
                    "$v=0; [void][U.A]::waveOutGetVolume([IntPtr]::Zero,[ref]$v); "
                    "Write-Output $v"
                )
                proc = run_powershell(script, timeout=25)
                if not ps_ok(proc):
                    return 0, False
                try:
                    raw = int((proc.stdout or "0").strip() or 0)
                except ValueError:
                    return 0, False
                return int(raw / 65535 * 100), bool(raw & 0x8000)

            current, muted = _volume_query()

            if mute is not None:
                target = 0 if mute else (current or 50)
            elif level is not None:
                target = max(0, min(int(level), 100))
            else:
                target = max(0, min(int(current) + int(adjust), 100))

            script = (
                "Add-Type -Namespace U -Name B -MemberDefinition '[DllImport(\"user32.dll\")] "
                "public static extern int waveOutSetVolume(IntPtr h, int v);'; "
                f"[void][U.B]::waveOutSetVolume([IntPtr]::Zero,{int(target / 100 * 65535)}); "
                "Write-Output 'ok'"
            )
            proc = run_powershell(script, timeout=25)
            if not ps_ok(proc):
                return {"error": f"could not set volume: {ps_error(proc)}"}
            return {"level": target, "muted": target == 0, "previous_level": current}

    def get_tools() -> list[Tool]:
        return [
            ListWindows(),
            GetActiveWindow(),
            ListProcesses(),
            KillProcess(),
            LockWorkstation(),
            EmptyRecycleBin(),
            ListDisplays(),
            GetBatteryStatus(),
            ShowDesktopNotification(),
            OpenWindowsTool(),
            SetSystemVolume(),
        ]


__all__ = ["get_tools"]
