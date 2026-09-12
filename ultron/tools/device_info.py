"""Device information tools — WiFi, network, location, device status."""

from __future__ import annotations

from typing import Any, Dict

from ultron.tools._termux import run_termux, run_cmd, run_settings, run_dumpsys
from ultron.tools.base import Tool


class GetDeviceInfo(Tool):
    """Get device model, manufacturer, Android version, and more."""

    name = "get_device_info"
    description = "Get Android device info: model, manufacturer, Android version, SDK, screen size."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "manufacturer": {"type": "string"},
            "android_version": {"type": "string"},
            "sdk_version": {"type": "string"},
            "screen_resolution": {"type": "string"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        model = run_cmd(["getprop", "ro.product.model"])
        manufacturer = run_cmd(["getprop", "ro.product.manufacturer"])
        android_ver = run_cmd(["getprop", "ro.build.version.release"])
        sdk_ver = run_cmd(["getprop", "ro.build.version.sdk"])
        resolution = run_cmd(["wm", "size"])

        return {
            "model": model.stdout.strip(),
            "manufacturer": manufacturer.stdout.strip(),
            "android_version": android_ver.stdout.strip(),
            "sdk_version": sdk_ver.stdout.strip(),
            "screen_resolution": resolution.stdout.strip(),
        }


class GetNetworkInfo(Tool):
    """Get WiFi connection details and network info."""

    name = "get_network_info"
    description = "Get current WiFi SSID, IP address, MAC address, and signal strength."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "ssid": {"type": "string"},
            "bssid": {"type": "string"},
            "ip": {"type": "string"},
            "mac": {"type": "string"},
            "signal_strength": {"type": "string"},
            "link_speed": {"type": "string"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("wifi-connectioninfo", parse_json=True)
        if not result.ok:
            return {"error": result.stderr}

        data = result.data if isinstance(result.data, dict) else {}
        return {
            "ssid": data.get("ssid", "unknown"),
            "bssid": data.get("bssid", "unknown"),
            "ip": data.get("ip", "unknown"),
            "mac": data.get("mac", "unknown"),
            "signal_strength": str(data.get("signal_strength", "unknown")),
            "link_speed": str(data.get("link_speed", "unknown")),
        }


class GetLocation(Tool):
    """Get the current GPS location."""

    name = "get_location"
    description = "Get current GPS location (latitude, longitude, accuracy). Requires GPS or network location."
    parameters = {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "description": "Location provider: gps, network, or passive. Default: network.",
                "default": "network",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "latitude": {"type": "number"},
            "longitude": {"type": "number"},
            "accuracy": {"type": "number"},
            "provider": {"type": "string"},
        },
    }

    def run(self, provider: str = "network", **kwargs: Any) -> Dict[str, Any]:
        p = kwargs.get("mode") or provider
        result = run_termux("location", args=["-p", p, "-r", "once"], parse_json=True)
        if not result.ok:
            return {"error": result.stderr, "latitude": 0, "longitude": 0}

        data = result.data if isinstance(result.data, dict) else {}
        return {
            "latitude": data.get("latitude", 0),
            "longitude": data.get("longitude", 0),
            "accuracy": data.get("accuracy", 0),
            "provider": data.get("provider", p),
        }


class ScanWifi(Tool):
    """Scan for available WiFi networks."""

    name = "scan_wifi"
    description = "Scan for available WiFi networks and return list with SSIDs and signal strength."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "networks": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_termux("wifi-scaninfo", parse_json=True)
        if not result.ok:
            return {"networks": [], "count": 0, "error": result.stderr}

        networks = result.data if isinstance(result.data, list) else []
        return {"networks": networks, "count": len(networks)}


class GetRunningApps(Tool):
    """Get list of currently running apps/processes."""

    name = "get_running_apps"
    description = "List currently running apps or processes on the device."
    parameters = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Filter processes by name (optional).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "processes": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, filter: str = "", **kwargs: Any) -> Dict[str, Any]:
        f = kwargs.get("query") or filter or ""
        result = run_cmd(["ps"])
        if not result.ok:
            return {"processes": [], "count": 0, "error": result.stderr}

        lines = result.stdout.strip().split("\n")
        processes = []
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 9:
                proc = {
                    "user": parts[0],
                    "pid": parts[1],
                    "vsize": parts[2],
                    "rss": parts[3],
                    "name": parts[8],
                }
                if f and f.lower() not in proc["name"].lower():
                    continue
                processes.append(proc)

        truncated = processes[:50]
        return {"processes": truncated, "count": len(truncated)}


class GetInstalledApps(Tool):
    """List all installed apps on the device."""

    name = "get_installed_apps"
    description = "List all installed packages/apps on the Android device."
    parameters = {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Filter apps by name (optional).",
            },
        },
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "apps": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def run(self, filter: str = "", **kwargs: Any) -> Dict[str, Any]:
        f = kwargs.get("query") or filter or ""
        result = run_cmd(["pm", "list", "packages", "-3"])  # third-party apps
        if not result.ok:
            return {"apps": [], "count": 0, "error": result.stderr}

        lines = result.stdout.strip().split("\n")
        apps = []
        for line in lines:
            pkg = line.replace("package:", "").strip()
            if f and f.lower() not in pkg.lower():
                continue
            apps.append(pkg)

        return {"apps": sorted(apps)[:200], "count": len(apps[:200])}


class GetStorageInfo(Tool):
    """Get device storage information."""

    name = "get_storage"
    description = "Get device storage info: total, used, available space."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "total_bytes": {"type": "integer"},
            "used_bytes": {"type": "integer"},
            "available_bytes": {"type": "integer"},
            "total_human": {"type": "string"},
            "available_human": {"type": "string"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["df", "/sdcard"])
        if not result.ok:
            return {"error": result.stderr}

        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return {"error": "Could not parse storage info"}

        parts = lines[1].split()
        # /sdcard output: Filesystem  1K-blocks  Used  Available  Use%  Mounted_on
        if len(parts) >= 4:
            try:
                total = int(parts[1]) * 1024
                used = int(parts[2]) * 1024
                available = int(parts[3]) * 1024
                return {
                    "total_bytes": total,
                    "used_bytes": used,
                    "available_bytes": available,
                    "total_human": _human_size(total),
                    "available_human": _human_size(available),
                }
            except ValueError:
                pass

        return {"error": "Could not parse storage output"}


class GetMemoryInfo(Tool):
    """Get device RAM/memory information."""

    name = "get_memory"
    description = "Get device RAM/memory usage: total, available, and used."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "total_mb": {"type": "integer"},
            "available_mb": {"type": "integer"},
            "used_mb": {"type": "integer"},
        },
    }

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        result = run_cmd(["cat", "/proc/meminfo"])
        if not result.ok:
            return {"error": result.stderr}

        info = {}
        for line in result.stdout.strip().split("\n"):
            if line.startswith("MemTotal:"):
                info["total_mb"] = int(line.split()[1]) // 1024
            elif line.startswith("MemAvailable:"):
                info["available_mb"] = int(line.split()[1]) // 1024

        if "total_mb" in info and "available_mb" in info:
            info["used_mb"] = info["total_mb"] - info["available_mb"]
            return info
        return {"error": "Could not parse memory info"}


def _human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


__all__ = [
    "GetDeviceInfo",
    "GetNetworkInfo",
    "GetLocation",
    "ScanWifi",
    "GetRunningApps",
    "GetInstalledApps",
    "GetStorageInfo",
    "GetMemoryInfo",
]
