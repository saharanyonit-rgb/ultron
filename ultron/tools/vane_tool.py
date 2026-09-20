"""Vane search engine tool — Perplexity-style AI answers with cited sources.

Wraps the local Vane answering engine (Next.js app, http://127.0.0.1:3000)
so JARVIS can get LLM-generated answers backed by live web search with
citations. Vane runs SearxNG + an LLM/embedding provider on your own machine.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

from ultron.tools.base import Tool

DEFAULT_BASE_URL = "http://127.0.0.1:3000"

OPTIMIZATION_MODES = ("speed", "balanced", "quality")
SOURCE_TYPES = ("web", "academic", "discussions")


def _get_base_url() -> str:
    """Resolve the Vane base URL from env or default."""
    return os.environ.get("VANE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class VaneSearchTool(Tool):
    """Search via the local Vane AI answering engine and get a cited answer."""

    name = "vane_search"
    description = (
        "Run a Perplexity-style AI web search through the local Vane engine. Returns a "
        "cited, LLM-written answer synthesized from live search results. Use for open-ended "
        "questions, research, current events, or when you need an answer backed by citations. "
        "Modes: speed (fast), balanced (default), quality (deep research with page scraping). "
        "Sources: web, academic, discussions. Requires the Vane server running on port 3000 "
        "(`docker compose up` in the Vane repo) and a configured chat+embedding model."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The question or topic to research.",
            },
            "optimization_mode": {
                "type": "string",
                "enum": list(OPTIMIZATION_MODES),
                "description": "speed=quick, balanced=default, quality=deep multi-page research.",
                "default": "balanced",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string", "enum": list(SOURCE_TYPES)},
                "description": "Search sources. web=general pages, academic=papers, discussions=forums.",
                "default": ["web"],
            },
            "max_sources": {
                "type": "integer",
                "description": "Max source citations to return (1-10, default 5).",
                "default": 5,
            },
            "base_url": {
                "type": "string",
                "description": "Vane server URL (default http://127.0.0.1:3000, or VANE_BASE_URL env).",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "answer": {"type": "string"},
            "sources": {"type": "array"},
            "mode": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def _discover_models(self, client: httpx.Client, base: str) -> Optional[Dict[str, Dict[str, str]]]:
        """Find the first configured chat + embedding model from Vane's API."""
        try:
            resp = client.get(f"{base}/api/providers", timeout=10.0)
            resp.raise_for_status()
            providers = (resp.json() or {}).get("providers") or []
        except Exception:
            return None

        for prov in providers:
            pid = prov.get("id")
            chat = (prov.get("chatModels") or [])
            embed = (prov.get("embeddingModels") or [])
            if pid and chat and embed:
                return {
                    "chatModel": {"providerId": pid, "key": chat[0].get("key")},
                    "embeddingModel": {"providerId": pid, "key": embed[0].get("key")},
                }
        return None

    def run(
        self,
        query: str,
        optimization_mode: str = "balanced",
        sources: Optional[List[str]] = None,
        max_sources: int = 5,
        base_url: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"success": False, "error": "Missing required parameter 'query'."}

        if optimization_mode not in OPTIMIZATION_MODES:
            return {
                "success": False,
                "error": f"Unknown optimization_mode '{optimization_mode}'. Choose from: {', '.join(OPTIMIZATION_MODES)}",
            }

        srcs = [s for s in (sources or ["web"]) if s in SOURCE_TYPES]
        if not srcs:
            return {"success": False, "error": f"Unknown sources. Choose from: {', '.join(SOURCE_TYPES)}"}

        base = (base_url or _get_base_url()).rstrip("/")
        max_sources = max(1, min(int(max_sources or 5), 10))

        try:
            with httpx.Client(timeout=60.0) as client:
                try:
                    health = client.get(f"{base}/api/providers", timeout=10.0)
                    health.raise_for_status()
                except httpx.RequestError:
                    return {
                        "success": False,
                        "error": (
                            f"Vane is not reachable at {base}. Start it first: in the Vane repo run "
                            "`docker compose up -d`, then open http://localhost:3000 and complete the "
                            "setup (chat + embedding model)."
                        ),
                    }
                except httpx.HTTPStatusError as exc:
                    return {"success": False, "error": f"Vane at {base} returned HTTP {exc.response.status_code}."}

                models = self._discover_models(client, base)
                if models is None:
                    return {
                        "success": False,
                        "error": (
                            "Vane is running but has no configured models. Open http://localhost:3000 "
                            "and add a chat model + embedding model (or set OPENAI_API_KEY / OLLAMA_BASE_URL)."
                        ),
                    }

                payload = {
                    "query": query,
                    "optimizationMode": optimization_mode,
                    "sources": srcs,
                    "stream": False,
                    **models,
                }
                resp = client.post(f"{base}/api/search", json=payload, timeout=300.0)
                if resp.status_code >= 400:
                    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    return {
                        "success": False,
                        "error": f"Vane search failed (HTTP {resp.status_code}): {body.get('message') or resp.text[:500]}",
                    }

                data = resp.json()
                answer = (data.get("message") or "").strip()
                if not answer:
                    return {"success": False, "error": "Vane returned an empty answer."}

                raw_sources = data.get("sources") or []
                sources_out: List[Dict[str, str]] = []
                for src in raw_sources[:max_sources]:
                    meta = src.get("metadata") or {}
                    sources_out.append(
                        {
                            "title": str(meta.get("title") or ""),
                            "url": str(meta.get("url") or ""),
                            "content": str(src.get("content") or "")[:2000],
                        }
                    )
                return {
                    "success": True,
                    "answer": answer,
                    "sources": sources_out,
                    "mode": optimization_mode,
                }
        except httpx.TimeoutException:
            return {"success": False, "error": "Vane search timed out (300s). Try optimization_mode 'speed'."}
        except Exception as exc:
            return {"success": False, "error": f"Vane search error: {exc}"}