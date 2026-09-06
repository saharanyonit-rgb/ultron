"""V1 system info tool — OS/CPU/RAM/disk via stdlib + ctypes (no psutil)."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
from typing import Any, Dict

from ultron.tools.base import Tool


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


def _ram_gb() -> tuple[float, float]:
    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullTotalPhys / 1e9, status.ullAvailPhys / 1e9


def _uptime_seconds() -> int:
    try:
        return int(ctypes.windll.kernel32.GetTickCount64() // 1000)
    except Exception:
        return 0


def _drives() -> list[Dict[str, Any]]:
    result = []
    for drive in os.listdrives():
        drive = drive.strip("\\")
        if not drive:
            continue
        try:
            usage = shutil.disk_usage(drive + "\\")
            result.append(
                {
                    "drive": drive,
                    "total_gb": round(usage.total / 1e9, 1),
                    "free_gb": round(usage.free / 1e9, 1),
                }
            )
        except OSError:
            continue
    return result


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
            "cpu": platform.processor() or "unknown",
            "cpu_cores": os.cpu_count(),
            "ram_total_gb": round(total_gb, 1),
            "ram_available_gb": round(avail_gb, 1),
            "uptime_seconds": _uptime_seconds(),
            "python_version": platform.python_version(),
            "drives": _drives(),
        }
