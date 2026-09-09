"""Time and date tools — current time, timezone conversion, scheduling."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from ultron.tools.base import Tool


class GetCurrentTime(Tool):
    """Get the current date and time in any timezone."""
    name = "get_current_time"
    description = (
        "Get the current date and time. Optionally specify a timezone "
        "(e.g. 'Asia/Kolkata', 'US/Eastern', 'UTC'). Default is local time."
    )
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name like 'Asia/Kolkata', 'US/Eastern', 'UTC'. Default: local.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "datetime": {"type": "string"},
            "date": {"type": "string"},
            "time": {"type": "string"},
            "day_of_week": {"type": "string"},
            "timezone": {"type": "string"},
            "unix_timestamp": {"type": "integer"},
        },
    }
    mutates = False

    _TZ_MAP = {
        "india": "Asia/Kolkata",
        "ist": "Asia/Kolkata",
        "us/eastern": "US/Eastern",
        "us/pacific": "US/Pacific",
        "us/central": "US/Central",
        "uk": "Europe/London",
        "utc": "UTC",
        "gmt": "UTC",
        "japan": "Asia/Tokyo",
        "china": "Asia/Shanghai",
        "germany": "Europe/Berlin",
        "europe": "Europe/Berlin",
        "australia": "Australia/Sydney",
    }

    def run(self, timezone: str = "", **kwargs: Any) -> Dict[str, Any]:
        tz_name = (timezone or kwargs.get("tz") or "").strip().lower()

        if tz_name and tz_name in self._TZ_MAP:
            tz_name = self._TZ_MAP[tz_name]

        now = datetime.now()

        if tz_name:
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo(tz_name)
                now = now.astimezone(tz)
            except Exception:
                pass

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return {
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": days[now.weekday()],
            "timezone": str(now.tzinfo or "local"),
            "unix_timestamp": int(now.timestamp()),
        }


__all__ = ["GetCurrentTime"]