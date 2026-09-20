"""AgenticSeek tool — hand off autonomous multi-agent tasks to a local Manus-style backend.

Wraps the AgenticSeek FastAPI backend (http://127.0.0.1:7777). AgenticSeek uses
an agent router (casual / coder / file / browser / planner) to autonomously
plan, browse the web, write and run code, and produce a final answer. One task
at a time runs per backend process.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

from ultron.tools.base import Tool

DEFAULT_BASE_URL = "http://127.0.0.1:7777"


def _get_base_url() -> str:
    """Resolve the AgenticSeek backend URL from env or default."""
    return os.environ.get("AGENTICSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _get_token() -> Optional[str]:
    """Resolve the optional bearer token from env."""
    token = os.environ.get("AGENTICSEEK_API_TOKEN")
    return token.strip() if token else None


class AgenticSeekTaskTool(Tool):
    """Dispatch an autonomous multi-agent task to the local AgenticSeek backend."""

    name = "agenticseek_task"
    description = (
        "Hand a complex, multi-step task to the local AgenticSeek agent backend (Manus-style). "
        "AgenticSeek selects a specialist agent (planner, coder, browser, file, casual) and "
        "autonomously searches the web, writes/debugs/runs code, plans subtasks, and returns a "
        "final answer with reasoning and tool-execution blocks. Use for deep research, "
        "multi-file coding jobs, web automation, or tasks needing a plan. Requires the "
        "AgenticSeek backend on port 7777 (`docker compose up` in the agenticSeek repo) and an "
        "LLM provider. Tasks run sequentially; if the backend is busy it returns 429."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The task to execute, e.g. 'Build a small CLI tool that ...'.",
            },
            "tts_enabled": {
                "type": "boolean",
                "description": "Speak the answer with TTS (default false).",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Max seconds to wait for the agent to finish (default 600).",
                "default": 600,
            },
            "base_url": {
                "type": "string",
                "description": "AgenticSeek backend URL (default http://127.0.0.1:7777, or AGENTICSEEK_BASE_URL env).",
            },
            "token": {
                "type": "string",
                "description": "Optional bearer token, if AGENTICSEEK_API_TOKEN is set on the backend.",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "answer": {"type": "string"},
            "reasoning": {"type": "string"},
            "agent": {"type": "string"},
            "blocks": {"type": "object"},
            "done": {"type": "boolean"},
            "error": {"type": "string"},
        },
    }
    mutates = True

    def run(
        self,
        query: str,
        tts_enabled: bool = False,
        timeout: int = 600,
        base_url: str = "",
        token: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"success": False, "error": "Missing required parameter 'query'."}

        base = (base_url or _get_base_url()).rstrip("/")
        timeout = max(5, int(timeout))
        auth_token = token.strip() if token else _get_token()
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        payload = {"query": query, "tts_enabled": bool(tts_enabled)}

        try:
            with httpx.Client(timeout=timeout) as client:
                try:
                    health = client.get(f"{base}/health", timeout=10.0)
                    health.raise_for_status()
                except httpx.RequestError:
                    return {
                        "success": False,
                        "error": (
                            f"AgenticSeek is not reachable at {base}. Start it first: in the agenticSeek "
                            "repo copy `.env.example` to `.env`, set WORK_DIR, then run "
                            "`docker compose up` (or `./start_services.sh`)."
                        ),
                    }
                except httpx.HTTPStatusError as exc:
                    return {"success": False, "error": f"AgenticSeek at {base} returned HTTP {exc.response.status_code}."}

                is_active = False
                try:
                    active_resp = client.get(f"{base}/is_active", timeout=10.0)
                    is_active = bool((active_resp.json() or {}).get("is_active"))
                except Exception:
                    pass

                resp = client.post(f"{base}/query", json=payload, headers=headers)
                if resp.status_code == 429:
                    return {
                        "success": False,
                        "error": "AgenticSeek is busy running another task (429). Retry when it finishes.",
                    }
                if resp.status_code >= 400:
                    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    return {
                        "success": False,
                        "error": f"AgenticSeek task failed (HTTP {resp.status_code}): {body.get('error') or body.get('message') or resp.text[:500]}",
                    }

                data = resp.json()
                answer = (data.get("answer") or "").strip()
                if not answer:
                    return {"success": False, "error": "AgenticSeek returned an empty answer."}

                blocks = data.get("blocks") or {}
                if not isinstance(blocks, dict):
                    blocks = {}
                blocks_out: Dict[str, Dict[str, Any]] = {}
                for k, block in blocks.items():
                    if isinstance(block, dict):
                        blocks_out[k] = {
                            "tool": str(block.get("tool_type") or block.get("tool") or ""),
                            "block": str(block.get("block") or "")[:1000],
                            "feedback": str(block.get("feedback") or "")[:1000],
                            "success": bool(block.get("success")),
                        }

                return {
                    "success": data.get("success", "true") != "false",
                    "answer": answer,
                    "reasoning": (data.get("reasoning") or "").strip()[:4000],
                    "agent": data.get("agent_name") or "",
                    "blocks": blocks_out,
                    "done": data.get("done", "false") == "true",
                }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"AgenticSeek task did not finish within {timeout}s. The run may still be in progress.",
            }
        except Exception as exc:
            return {"success": False, "error": f"AgenticSeek request error: {exc}"}