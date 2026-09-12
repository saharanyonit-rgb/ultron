"""HTTP API tool for JARVIS pipeline."""

from __future__ import annotations

import httpx
from typing import Any, Dict, List, Optional

from ultron.tools.base import Tool


class HttpRequest(Tool):
    name = "http_request"
    description = (
        "Make HTTP requests to APIs or web services. "
        "Supports GET, POST, PUT, DELETE methods with headers and JSON body. "
        "Use for REST API calls, webhooks, or fetching JSON data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to request.",
            },
            "method": {
                "type": "string",
                "description": "HTTP method (GET, POST, PUT, DELETE).",
                "default": "GET",
                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers as key-value pairs.",
            },
            "body": {
                "type": "object",
                "description": "JSON body for POST/PUT requests.",
            },
            "params": {
                "type": "object",
                "description": "URL query parameters.",
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds.",
                "default": 30,
            },
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "status_code": {"type": "integer"},
            "headers": {"type": "object"},
            "body": {"type": "string"},
            "json": {"type": "object"},
            "error": {"type": "string"},
            "duration_ms": {"type": "number"},
        },
    }
    mutates = True

    def run(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        **_: Any,
    ) -> Dict[str, Any]:
        import time

        start = time.time()
        headers = headers or {}

        if "Content-Type" not in headers and body:
            headers["Content-Type"] = "application/json"

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=body,
                    params=params,
                )

            duration_ms = round((time.time() - start) * 1000, 2)
            result: Dict[str, Any] = {
                "success": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text,
                "duration_ms": duration_ms,
            }

            if response.headers.get("Content-Type", "").startswith("application/json"):
                try:
                    result["json"] = response.json()
                except Exception:
                    pass

            return result

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"Request timed out after {timeout}s",
                "duration_ms": round((time.time() - start) * 1000, 2),
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"Request failed: {e}",
                "duration_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2),
            }


class FetchJson(Tool):
    name = "fetch_json"
    description = "Fetch and parse JSON data from a URL."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch JSON from.",
            },
            "headers": {
                "type": "object",
                "description": "Optional headers.",
            },
            "key_path": {
                "type": "string",
                "description": "Dot-notation path to extract specific data (e.g., 'data.results.0.name').",
            },
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "data": {"type": "object"},
            "extracted": {"type": "any"},
        },
    }

    def run(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        key_path: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        import time

        start = time.time()
        headers = headers or {}

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "duration_ms": round((time.time() - start) * 1000, 2),
                }

            data = response.json()
            result: Dict[str, Any] = {
                "success": True,
                "data": data,
                "duration_ms": round((time.time() - start) * 1000, 2),
            }

            if key_path:
                keys = key_path.split(".")
                current = data
                for k in keys:
                    if isinstance(current, list) and k.isdigit():
                        idx = int(k)
                        current = current[idx] if idx < len(current) else None
                    elif isinstance(current, dict):
                        current = current.get(k)
                    else:
                        current = None
                    if current is None:
                        result["extracted"] = None
                        result["error"] = f"Path '{key_path}' not found"
                        break
                else:
                    result["extracted"] = current

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "duration_ms": round((time.time() - start) * 1000, 2),
            }


__all__ = [
    "HttpRequest",
    "FetchJson",
]
