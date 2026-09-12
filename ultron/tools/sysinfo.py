"""V1 system info tool — OS/CPU/RAM/disk, cross-platform (Windows, Linux, Android)."""

from __future__ import annotations

import os
import platform
import shutil
import socket
import string
from typing import Any, Dict

from ultron.platform import is_windows, is_posix
from ultron.tools.base import Tool


def _ram_gb_windows() -> tuple[float, float]:
    """Get RAM info via Windows ctypes."""
    import ctypes

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullTotalPhys / 1e9, status.ullAvailPhys / 1e9


def _ram_gb_posix() -> tuple[float, float]:
    """Get RAM info from /proc/meminfo (Linux/Android)."""
    try:
        with open("/proc/meminfo") as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                val = int(parts[1]) * 1024  # kB -> bytes
                mem[key] = val
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        return total / 1e9, available / 1e9
    except Exception:
        return 0.0, 0.0


def _ram_gb() -> tuple[float, float]:
    if is_windows():
        return _ram_gb_windows()
    return _ram_gb_posix()


def _uptime_seconds() -> int:
    if is_windows():
        try:
            import ctypes
            return int(ctypes.windll.kernel32.GetTickCount64() // 1000)
        except Exception:
            return 0
    # POSIX: read /proc/uptime
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


def _cpu_info() -> str:
    if is_windows():
        return platform.processor() or "unknown"
    # Linux/Android: read /proc/cpuinfo
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        # Fallback: try processor field
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Hardware"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def _drives() -> list[Dict[str, Any]]:
    if is_windows():
        result = []
        # os.listdrives() requires Python 3.13+; probe alphabetically instead
        # so this also runs on the supported 3.12 runtime.
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if not os.path.isdir(drive):
                continue
            try:
                usage = shutil.disk_usage(drive)
                result.append({
                    "drive": drive,
                    "total_gb": round(usage.total / 1e9, 1),
                    "free_gb": round(usage.free / 1e9, 1),
                })
            except OSError:
                continue
        return result
    # POSIX: just show root filesystem
    try:
        usage = shutil.disk_usage("/")
        return [{
            "drive": "/",
            "total_gb": round(usage.total / 1e9, 1),
            "free_gb": round(usage.free / 1e9, 1),
        }]
    except Exception:
        return []


class GetSystemInfo(Tool):
    name = "get_system_info"
    description = (
        "Return basic system information: OS, hostname, CPU, memory, disk usage "
        "and uptime."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "os": {"type": "string"},
            "os_version": {"type": "string"},
            "hostname": {"type": "string"},
            "machine": {"type": "string"},
            "cpu": {"type": "string"},
            "cpu_cores": {"type": "integer"},
            "ram_total_gb": {"type": "number"},
            "ram_available_gb": {"type": "number"},
            "uptime_seconds": {"type": "integer"},
            "python_version": {"type": "string"},
            "drives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drive": {"type": "string"},
                        "total_gb": {"type": "number"},
                        "free_gb": {"type": "number"},
                    },
                },
            },
        },
    }

    def run(self, **_: Any) -> Dict[str, Any]:
        total_gb, avail_gb = _ram_gb()
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "hostname": socket.gethostname(),
            "machine": platform.machine(),
            "cpu": _cpu_info(),
            "cpu_cores": os.cpu_count(),
            "ram_total_gb": round(total_gb, 1),
            "ram_available_gb": round(avail_gb, 1),
            "uptime_seconds": _uptime_seconds(),
            "python_version": platform.python_version(),
            "drives": _drives(),
        }
