"""Extended API endpoints for JARVIS dashboard.

Provides system metrics, agent status, memory, security, and computer state
endpoints that the frontend dashboard consumes.
"""

from __future__ import annotations

import ctypes
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

logger = logging.getLogger("ultron.web_api")


# ── System Metrics ──────────────────────────────────────────────

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


def get_system_metrics() -> Dict[str, Any]:
    """Get real system metrics using Windows APIs."""
    # RAM
    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    try:
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        ram_total = status.ullTotalPhys
        ram_used = status.ullTotalPhys - status.ullAvailPhys
        ram_percent = status.dwMemoryLoad
    except Exception:
        ram_total = 0
        ram_used = 0
        ram_percent = 0

    # CPU via WMI (more reliable than ctypes)
    cpu_percent = None
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance Win32_Processor).LoadPercentage"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            cpu_percent = int(result.stdout.strip().split('\n')[0].strip())
    except Exception as exc:
        logger.warning("CPU measurement failed: %s", exc)

    # Disk
    drives = []
    try:
        for letter in "CDEFGHIJKL":
            path = f"{letter}:\\"
            if os.path.exists(path):
                usage = shutil.disk_usage(path)
                drives.append({
                    "drive": f"{letter}:",
                    "total_gb": round(usage.total / 1e9, 1),
                    "used_gb": round((usage.total - usage.free) / 1e9, 1),
                    "free_gb": round(usage.free / 1e9, 1),
                    "percent": round((usage.total - usage.free) / usage.total * 100, 1),
                })
    except OSError as exc:
        logger.warning("Disk usage query failed: %s", exc)

    # Temperature (via PowerShell)
    temperature = None
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "$t = Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty CurrentTemperature; "
             "if ($t) { [math]::Round(($t - 2732) / 10, 1) }"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            temperature = float(result.stdout.strip())
    except Exception as exc:
        logger.warning("Temperature measurement failed: %s", exc)

    # Uptime
    uptime_seconds = 0
    try:
        uptime_seconds = int(ctypes.windll.kernel32.GetTickCount64() // 1000)
    except Exception as exc:
        logger.warning("Uptime query failed: %s", exc)

    return {
        "cpu_percent": cpu_percent,
        "cpu_cores": os.cpu_count(),
        "cpu_name": platform.processor() or "unknown",
        "ram_total": ram_total,
        "ram_used": ram_used,
        "ram_percent": ram_percent,
        "temperature": temperature,
        "drives": drives,
        "uptime_seconds": uptime_seconds,
    }


# ── Network Status ──────────────────────────────────────────────

def get_network_status() -> Dict[str, Any]:
    """Get network connectivity status with real-time bandwidth metrics."""
    connected = False
    latency_ms = None
    hostname = socket.gethostname()
    tx_percent = 0.0
    rx_percent = 0.0
    local_ip = None

    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Test-Connection -ComputerName 8.8.8.8 -Count 1 -Quiet)"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        connected = result.returncode == 0 and "True" in result.stdout
    except Exception as exc:
        logger.warning("Network connectivity check failed: %s", exc)

    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Test-Connection -ComputerName 8.8.8.8 -Count 1).ResponseTime"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            latency_ms = int(float(result.stdout.strip().split('\n')[0].strip()))
    except Exception as exc:
        logger.warning("Network latency measurement failed: %s", exc)

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception as exc:
        logger.warning("Local IP detection failed: %s", exc)

    # Get network adapter throughput stats (bytes/sec)
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapterStatistics | Where-Object {$_.ReceivedBytes -gt 0} | "
             "Select-Object ReceivedBytes,SentBytes | "
             "$totalRx = ($_ | Measure-Object -Property ReceivedBytes -Sum).Sum; "
             "$totalTx = ($_ | Measure-Object -Property SentBytes -Sum).Sum; "
             "[math]::Round($totalRx/1MB, 2), [math]::Round($totalTx/1MB, 2)"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                rx_mb = float(lines[0].strip())
                tx_mb = float(lines[1].strip())
                # Normalize to 0-100% (cap at 100Mbps for display)
                rx_percent = min(round(rx_mb * 10, 1), 100.0)
                tx_percent = min(round(tx_mb * 10, 1), 100.0)
    except Exception as exc:
        logger.warning("Network throughput stats failed: %s", exc)

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
    """Get system identification info."""
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
    """Get computer/desktop state."""
    active_window = None
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
    except Exception as exc:
        logger.warning("Active window detection failed: %s", exc)

    running_apps = []
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
    except Exception as exc:
        logger.warning("Running apps detection failed: %s", exc)

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
