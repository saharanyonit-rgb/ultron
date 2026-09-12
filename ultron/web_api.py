"""Extended API endpoints for JARVIS dashboard — cross-platform.

Provides system metrics, agent status, memory, security, and computer state
endpoints that the frontend dashboard consumes.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.platform import is_windows

logger = logging.getLogger("ultron.web_api")


# ── System Metrics ──────────────────────────────────────────────

def _get_ram_info_windows() -> tuple[int, int, int]:
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
    return status.ullTotalPhys, status.ullTotalPhys - status.ullAvailPhys, status.dwMemoryLoad


def _get_ram_info_posix() -> tuple[int, int, int]:
    """Get RAM info from /proc/meminfo."""
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
        used = total - available
        percent = int(used / total * 100) if total > 0 else 0
        return total, used, percent
    except Exception:
        return 0, 0, 0


def _get_cpu_percent_windows() -> Optional[int]:
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_Processor).LoadPercentage"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0].strip())
    except Exception:
        pass
    return None


def _get_cpu_percent_posix() -> Optional[int]:
    """Read CPU usage from /proc/stat."""
    try:
        def read_cpu():
            with open("/proc/stat") as f:
                line = f.readline()
            parts = line.split()
            # /proc/stat first line: cpu user nice system idle iowait irq softirq steal
            return int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])

        user1, nice1, system1, idle1 = read_cpu()
        time.sleep(0.1)
        user2, nice2, system2, idle2 = read_cpu()

        idle = idle2 - idle1
        total = (user2 + nice2 + system2 + idle2) - (user1 + nice1 + system1 + idle1)
        if total == 0:
            return 0
        return int((total - idle) / total * 100)
    except Exception:
        return None


def _get_temperature_windows() -> Optional[float]:
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$t = Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' -ErrorAction SilentlyContinue | "
             "Select-Object -First 1 -ExpandProperty CurrentTemperature; "
             "if ($t) { [math]::Round(($t - 2732) / 10, 1) }"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _get_temperature_posix() -> Optional[float]:
    """Read CPU temperature from thermal zones."""
    thermal_paths = [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ]
    for path in thermal_paths:
        try:
            with open(path) as f:
                temp = int(f.read().strip()) / 1000
                return round(temp, 1)
        except (OSError, ValueError):
            continue
    return None


def _get_drives() -> list[Dict[str, Any]]:
    drives = []
    if is_windows():
        for letter in "CDEFGHIJKL":
            path = f"{letter}:\\"
            if os.path.exists(path):
                try:
                    usage = shutil.disk_usage(path)
                    drives.append({
                        "drive": f"{letter}:",
                        "total_gb": round(usage.total / 1e9, 1),
                        "used_gb": round((usage.total - usage.free) / 1e9, 1),
                        "free_gb": round(usage.free / 1e9, 1),
                        "percent": round((usage.total - usage.free) / usage.total * 100, 1),
                    })
                except OSError:
                    continue
    else:
        try:
            usage = shutil.disk_usage("/")
            drives.append({
                "drive": "/",
                "total_gb": round(usage.total / 1e9, 1),
                "used_gb": round((usage.total - usage.free) / 1e9, 1),
                "free_gb": round(usage.free / 1e9, 1),
                "percent": round((usage.total - usage.free) / usage.total * 100, 1),
            })
        except OSError:
            pass
    return drives


def _get_uptime() -> int:
    if is_windows():
        try:
            import ctypes
            return int(ctypes.windll.kernel32.GetTickCount64() // 1000)
        except Exception:
            return 0
    try:
        with open("/proc/uptime") as f:
            return int(float(f.read().split()[0]))
    except Exception:
        return 0


def get_system_metrics() -> Dict[str, Any]:
    """Get real system metrics — cross-platform."""
    if is_windows():
        ram_total, ram_used, ram_percent = _get_ram_info_windows()
        cpu_percent = _get_cpu_percent_windows()
        temperature = _get_temperature_windows()
    else:
        ram_total, ram_used, ram_percent = _get_ram_info_posix()
        cpu_percent = _get_cpu_percent_posix()
        temperature = _get_temperature_posix()

    return {
        "cpu_percent": cpu_percent,
        "cpu_cores": os.cpu_count(),
        "cpu_name": platform.processor() or "unknown",
        "ram_total": ram_total,
        "ram_used": ram_used,
        "ram_percent": ram_percent,
        "temperature": temperature,
        "drives": _get_drives(),
        "uptime_seconds": _get_uptime(),
    }


# ── Network Status ──────────────────────────────────────────────

def get_network_status() -> Dict[str, Any]:
    """Get network connectivity status — cross-platform."""
    connected = False
    latency_ms = None
    hostname = socket.gethostname()
    tx_percent = 0.0
    rx_percent = 0.0
    local_ip = None

    # Check connectivity
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("8.8.8.8", 80))
        connected = result == 0
        sock.close()
    except Exception:
        pass

    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Latency
    if connected:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            start = time.time()
            sock.connect(("8.8.8.8", 80))
            latency_ms = int((time.time() - start) * 1000)
            sock.close()
        except Exception:
            pass

    return {
        "connected": connected,
        "hostname": hostname,
        "local_ip": local_ip,
        "latency_ms": latency_ms,
        "connection_type": "wifi" if connected else "disconnected",
        "tx_percent": tx_percent,
        "rx_percent": rx_percent,
    }


# ── OS / Version Info ───────────────────────────────────────────

def get_system_info() -> Dict[str, Any]:
    """Get system identification info — cross-platform."""
    os_name = f"{platform.system()} {platform.release()}"
    return {
        "os": os_name,
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "python_version": platform.python_version(),
        "hostname": socket.gethostname(),
    }


# ── Agent Status ────────────────────────────────────────────────

def get_agent_status() -> List[Dict[str, Any]]:
    """Get status of all registered agents."""
    agents = [
        {"name": "ORCHESTRATOR", "type": "orchestrator", "description": "Central execution coordinator"},
        {"name": "CODING AGENT", "type": "coding", "description": "Code analysis, generation, and debugging"},
        {"name": "RESEARCH AGENT", "type": "research", "description": "Web research and information gathering"},
        {"name": "BROWSER AGENT", "type": "browser", "description": "Web navigation and interaction"},
        {"name": "VISION AGENT", "type": "vision", "description": "Screen capture and visual analysis"},
        {"name": "WRITING AGENT", "type": "writing", "description": "Document creation and editing"},
        {"name": "COMMUNICATION AGENT", "type": "communication", "description": "Email, messaging, notifications"},
    ]

    for agent in agents:
        agent["status"] = "offline"
        agent["current_task"] = None
        agent["last_active"] = None

    return agents


# ── Memory Status ───────────────────────────────────────────────

def get_memory_status() -> Dict[str, Any]:
    """Get memory subsystem status."""
    return {
        "working_memory": {"status": "inactive", "entries": 0},
        "conversation_memory": {"status": "inactive", "entries": 0},
        "project_memory": {"status": "inactive", "entries": 0},
        "long_term_memory": {"status": "inactive", "entries": 0},
    }


# ── Security Status ─────────────────────────────────────────────

def get_security_status() -> Dict[str, Any]:
    """Get security/permission status."""
    return {
        "risk_level": "low",
        "policy": "standard",
        "permissions": {
            "filesystem_read": "allowed",
            "filesystem_write": "allowed",
            "command_execution": "allowed",
            "browser_access": "allowed",
            "destructive_action": "approval_required",
        },
        "pending_approvals": 0,
        "recent_events": [],
    }


# ── Computer State ──────────────────────────────────────────────

def get_computer_state() -> Dict[str, Any]:
    """Get computer/desktop state — cross-platform."""
    active_window = None
    running_apps = []

    if is_windows():
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object -First 1 MainWindowTitle | ForEach-Object { $_.MainWindowTitle }"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                active_window = result.stdout.strip().split('\n')[0].strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object -Unique ProcessName | ForEach-Object { $_.ProcessName }"],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                running_apps = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()][:10]
        except Exception:
            pass
    else:
        # Linux/Android: use ps
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-pcpu"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:11]  # skip header, top 10
                running_apps = [line.split()[10] for line in lines if len(line.split()) > 10]
        except Exception:
            pass

    return {
        "active_window": active_window,
        "running_applications": running_apps,
        "screen_state": "available",
        "automation_ready": True,
    }


# ── Orchestrator State ──────────────────────────────────────────

def get_orchestrator_state(orchestrator: Any = None) -> Dict[str, Any]:
    """Get current orchestrator state for the core visualization."""
    if orchestrator is None:
        return {
            "state": "idle",
            "online": False,
            "current_goal": None,
            "progress": 0.0,
        }

    state = getattr(orchestrator, "_state", "idle")
    goal = getattr(orchestrator, "_current_goal", None)
    graph = getattr(orchestrator, "_current_graph", None)

    progress = 0.0
    if graph and hasattr(graph, "progress"):
        progress = graph.progress

    goal_info = None
    if goal and hasattr(goal, "description"):
        goal_info = {
            "id": getattr(goal, "id", ""),
            "description": getattr(goal, "description", ""),
            "status": getattr(goal, "status", "unknown").value if hasattr(getattr(goal, "status", ""), "value") else str(getattr(goal, "status", "unknown")),
        }

    return {
        "state": state.value if hasattr(state, "value") else str(state),
        "online": True,
        "current_goal": goal_info,
        "progress": progress,
    }


# ── Voice State ────────────────────────────────────────────────

def get_voice_state() -> Dict[str, Any]:
    """Get current voice engine state."""
    try:
        from ultron.tools.voice import get_voice_engine
        engine = get_voice_engine()
        return {
            "state": engine.state.value,
            "available": True,
        }
    except Exception:
        return {
            "state": "unavailable",
            "available": False,
        }
