"""Additive read-only web modules for the JARVIS console.

These are purely additive endpoints used by the new frontend. Nothing in the
existing JARVIS behaviour depends on this module, and no existing endpoint is
changed or removed.

* ``GET /api/weather`` - current conditions and a short daily forecast from
  Open-Meteo (no API key required).
* ``GET /api/news``    - a small set of headlines parsed from public RSS feeds.

Both are cached for a short period and degrade honestly: on failure the caller
receives a 502 with a reason instead of fabricated data.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

logger = logging.getLogger("ultron.web_modules")

WEATHER_CACHE_TTL = 600.0
NEWS_CACHE_TTL = 900.0
UPSTREAM_TIMEOUT = 8.0
USER_AGENT = "JARVIS-Consulton/1.0 (+local dashboard)"

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Violent rain showers",
    85: "Snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with hail",
}

NEWS_FEEDS: List[Dict[str, str]] = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml", "source": "BBC World"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "source": "BBC Technology"},
    {"url": "https://hnrss.org/frontpage", "source": "Hacker News"},
]

_lock = threading.Lock()
_cache: Dict[str, Any] = {}


def _cache_get(key: str, ttl: float) -> Any:
    with _lock:
        entry = _cache.get(key)
    if not entry:
        return None
    stored_at, value = entry
    if time.time() - stored_at > ttl:
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    with _lock:
        _cache[key] = (time.time(), value)


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT) as response:
        return response.read()


def _describe(code: Any) -> str:
    try:
        return WMO_CODES.get(int(code), "Unknown conditions")
    except (TypeError, ValueError):
        return "Unknown conditions"


# ── Weather ─────────────────────────────────────────────────────

def get_weather(place: Optional[str] = None, lat: Optional[float] = None,
                lon: Optional[float] = None) -> Dict[str, Any]:
    """Return current conditions plus a short daily forecast.

    Accepts either a free-text ``place`` or explicit coordinates. When nothing
    is supplied the most recently requested location is reused, and failing
    that the caller's own IP is not geolocated - the response simply reports
    that a location is required.
    """
    cache_key = f"weather:{place or ''}:{lat}:{lon}"
    cached = _cache_get(cache_key, WEATHER_CACHE_TTL)
    if cached is not None:
        return cached

    location_name, latitude, longitude = _resolve_location(place, lat, lon)

    query = (
        f"?latitude={latitude:.4f}&longitude={longitude:.4f}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m,is_day"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
        "&forecast_days=5&timezone=auto"
    )
    raw = _fetch(FORECAST_URL + query)
    data = json.loads(raw.decode("utf-8"))

    current = data.get("current", {}) or {}
    daily = data.get("daily", {}) or {}

    result: Dict[str, Any] = {
        "location": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": data.get("timezone"),
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "apparent_c": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "wind_kph": current.get("wind_speed_10m"),
            "is_day": current.get("is_day"),
            "description": _describe(current.get("weather_code")),
            "observed_at": current.get("time"),
        },
        "daily": _build_daily(daily),
        "source": "open-meteo.com",
        "fetched_at": time.time(),
    }
    _cache_set(cache_key, result)
    # Remember the resolved location so a later request without arguments can
    # reuse it (see _resolve_location).
    _cache_set("weather:last", result)
    return result


def _build_daily(daily: Dict[str, Any]) -> List[Dict[str, Any]]:
    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    rain = daily.get("precipitation_probability_max") or []

    rows: List[Dict[str, Any]] = []
    for index, date in enumerate(dates):
        rows.append({
            "date": date,
            "max_c": highs[index] if index < len(highs) else None,
            "min_c": lows[index] if index < len(lows) else None,
            "precipitation_pct": rain[index] if index < len(rain) else None,
            "description": _describe(codes[index] if index < len(codes) else None),
        })
    return rows


def _resolve_location(place: Optional[str], lat: Optional[float], lon: Optional[float]
                      ) -> tuple[str, float, float]:
    if lat is not None and lon is not None:
        return (place or f"{lat:.3f}, {lon:.3f}", float(lat), float(lon))

    query = place or ""
    if not query:
        with _lock:
            last = _cache.get("weather:last")
        if last:
            _, cached = last
            return cached["location"], cached["latitude"], cached["longitude"]
        raise LookupError("No location supplied and no previous location cached")

    data = json.loads(_fetch(f"{GEOCODE_URL}?name={urllib.parse.quote(query)}&count=1").decode("utf-8"))
    results = data.get("results") or []
    if not results:
        raise LookupError(f"Location not found: {query}")

    hit = results[0]
    name = hit.get("name", query)
    admin = hit.get("admin1")
    country = hit.get("country")
    label = ", ".join(part for part in (name, admin, country) if part)
    return label, float(hit["latitude"]), float(hit["longitude"])


# ── News ───────────────────────────────────────────────────────

def get_news(limit: int = 12) -> Dict[str, Any]:
    """Return headlines gathered from public RSS feeds."""
    cached = _cache_get("news", NEWS_CACHE_TTL)
    if cached is not None:
        return cached

    items: List[Dict[str, Any]] = []
    errors: List[str] = []

    for feed in NEWS_FEEDS:
        try:
            items.extend(_parse_feed(feed))
        except (urllib.error.URLError, OSError, ElementTree.ParseError, ValueError) as exc:
            errors.append(f"{feed['source']}: {exc}")
            logger.debug("news feed failed: %s", exc)

    items.sort(key=lambda item: item.get("_sort", 0), reverse=True)
    result_items = [
        {k: v for k, v in item.items() if k != "_sort"}
        for item in items[: max(1, limit)]
    ]

    if not result_items:
        raise ConnectionError("All news feeds failed: " + "; ".join(errors))

    payload = {"items": result_items, "sources": [f["source"] for f in NEWS_FEEDS],
               "fetched_at": time.time()}
    _cache_set("news", payload)
    return payload


def _parse_feed(feed: Dict[str, str]) -> List[Dict[str, Any]]:
    root = ElementTree.fromstring(_fetch(feed["url"]))
    rows: List[Dict[str, Any]] = []

    for node in root.iter("item"):
        title = _text(node, "title")
        if not title:
            continue
        published = _text(node, "pubDate")
        rows.append({
            "title": title.strip(),
            "link": (_text(node, "link") or "").strip(),
            "summary": _summary(_text(node, "description")),
            "published": _iso(published),
            "source": feed["source"],
            "_sort": _timestamp(published),
        })
    return rows


def _text(node: ElementTree.Element, tag: str) -> Optional[str]:
    child = node.find(tag)
    if child is None or child.text is None:
        return None
    return child.text


def _summary(raw: Optional[str]) -> str:
    if not raw:
        return ""
    text = ElementTree.fromstring(f"<div>{raw}</div>").itertext()
    cleaned = " ".join(" ".join(text).split())
    return cleaned[:240]


def _timestamp(published: Optional[str]) -> float:
    if not published:
        return 0.0
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(published).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _iso(published: Optional[str]) -> Optional[str]:
    if not published:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(published).isoformat()
    except (TypeError, ValueError):
        return None
