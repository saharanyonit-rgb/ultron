"""UI/UX Pro Max — searchable design intelligence as an Ultron tool.

Wraps the UI/UX Pro Max skill's BM25 search engine (installed under
.opencode/skills/ui-ux-pro-max/) so Ultron can look up UI styles, color
palettes, font pairings, chart types, UX guidelines, icons, landing-page
patterns, and stack-specific implementation rules from local CSV databases.

The underlying skill is a CLI search script; this tool shells out to it with
--json and returns the structured results, so the skill stays the source of
truth and needs no bundled copy of its data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ultron.tools.base import Tool

SCRIPT_REL = Path(".opencode") / "skills" / "ui-ux-pro-max" / "scripts" / "search.py"

DOMAINS = [
    "product",
    "style",
    "typography",
    "color",
    "landing",
    "chart",
    "ux",
    "icons",
    "react",
    "web",
    "google-fonts",
    "gsap",
]

STACKS = [
    "react",
    "nextjs",
    "vue",
    "svelte",
    "astro",
    "swiftui",
    "react-native",
    "flutter",
    "nuxtjs",
    "nuxt-ui",
    "html-tailwind",
    "shadcn",
    "jetpack-compose",
    "threejs",
    "angular",
    "laravel",
    "javafx",
    "wpf",
    "winui",
    "avalonia",
    "uno",
    "uwp",
]


def _find_skill_dir() -> Optional[Path]:
    """Locate the UI/UX Pro Max skill install, or the repo source, if any.

    Search order:
    1. UIUX_PRO_MAX_SKILL_DIR env var (explicit override)
    2. ultron/skills/ui-ux-pro-max  (Ultron-native bundled copy)
    3. .opencode/skills/ui-ux-pro-max  (opencode project-local install)
    4. ~/.opencode/skills/ui-ux-pro-max  (opencode global install)
    5. cloned repo fallback at project root
    """
    env_dir = os.environ.get("UIUX_PRO_MAX_SKILL_DIR")
    if env_dir and Path(env_dir).is_dir():
        return Path(env_dir)

    pkg_root = Path(__file__).resolve().parent.parent.parent
    cwd = Path.cwd()

    candidates: List[Path] = [
        pkg_root / "ultron" / "skills" / "ui-ux-pro-max",
        cwd / ".opencode" / "skills" / "ui-ux-pro-max",
        Path.home() / ".opencode" / "skills" / "ui-ux-pro-max",
        cwd / "ui-ux-pro-max-skill" / "src" / "ui-ux-pro-max",
        pkg_root / "ui-ux-pro-max-skill" / "src" / "ui-ux-pro-max",
    ]

    for cand in candidates:
        if (cand / "scripts" / "search.py").is_file():
            return cand
    return None


class SearchUIDesignTool(Tool):
    """Search the UI/UX Pro Max design-intelligence database."""

    name = "search_ui_design"
    description = (
        "Search a local UI/UX design-intelligence database for styles, color "
        "palettes, font pairings, UX guidelines, chart types, icons, and "
        "stack-specific implementation guidance (BM25 over curated CSV data). "
        "Use when designing, building, reviewing, or fixing interfaces. "
        "Provide a search query (e.g. 'glassmorphism dashboard') and optionally "
        "a domain (style, color, chart, landing, product, ux, typography, icons, "
        "gsap, react, web, google-fonts) or a stack (react, nextjs, vue, svelte, "
        "astro, swiftui, react-native, flutter, html-tailwind, shadcn, and more)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look up, e.g. 'saas landing page', 'glassmorphism', 'data table chart'.",
            },
            "domain": {
                "type": "string",
                "enum": DOMAINS,
                "description": "Search domain. Auto-detected if omitted.",
            },
            "stack": {
                "type": "string",
                "enum": STACKS,
                "description": "Stack-specific implementation guidelines, e.g. 'react' or 'html-tailwind'.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "Max results to return (default 3).",
            },
            "design_system": {
                "type": "boolean",
                "description": "Generate a complete design-system recommendation instead of a plain search.",
            },
            "project_name": {
                "type": "string",
                "description": "Project name for design-system output.",
            },
            "variance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Design variance dial (1=centered/minimal, 10=bold/asymmetric). Only with design_system.",
            },
            "motion": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Motion intensity dial (1=subtle, 10=complex); attaches a GSAP snippet. Only with design_system.",
            },
            "density": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Visual density dial (1=spacious, 10=dense/dashboard). Only with design_system.",
            },
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "count": {"type": "integer"},
            "query": {"type": "string"},
            "domain": {"type": "string"},
            "stack": {"type": "string"},
            "results": {"type": "array"},
            "design_system": {"type": "object"},
            "skill_dir": {"type": "string"},
            "error": {"type": "string"},
        },
    }
    mutates = False

    def _resolve_search_script(self) -> Optional[Path]:
        skill_dir = _find_skill_dir()
        if not skill_dir:
            return None
        script = skill_dir / "scripts" / "search.py"
        return script if script.is_file() else None

    def run(
        self,
        query: str,
        domain: str = "",
        stack: str = "",
        max_results: int = 3,
        design_system: bool = False,
        project_name: str = "",
        variance: int = 0,
        motion: int = 0,
        density: int = 0,
        **_: Any,
    ) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {"found": False, "error": "Missing required parameter 'query'."}

        if domain and stack:
            return {"found": False, "error": "Provide either 'domain' or 'stack', not both."}

        script = self._resolve_search_script()
        if script is None:
            return {
                "found": False,
                "error": (
                    "UI/UX Pro Max skill not found. Install it first with: "
                    "npx ui-ux-pro-max-cli init --ai opencode"
                ),
            }

        cmd: List[str] = [sys.executable, str(script), query, "--json"]
        if domain:
            if domain not in DOMAINS:
                return {"found": False, "error": f"Unknown domain '{domain}'. Choose from: {', '.join(DOMAINS)}"}
            cmd += ["--domain", domain]
        if stack:
            if stack not in STACKS:
                return {"found": False, "error": f"Unknown stack '{stack}'. Choose from: {', '.join(STACKS)}"}
            cmd += ["--stack", stack]
        if max_results not in (None, 0):
            cmd += ["--max-results", str(max(1, min(int(max_results), 20)))]
        if design_system:
            cmd += ["--design-system"]
            if project_name:
                cmd += ["--project-name", project_name]
            for flag, val in (("--variance", variance), ("--motion", motion), ("--density", density)):
                if val in (None, 0):
                    continue
                cmd += [flag, str(max(1, min(int(val), 10)))]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(script.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            return {"found": False, "error": "UI/UX Pro Max search timed out after 120s."}
        except OSError as exc:
            return {"found": False, "error": f"Could not run UI/UX Pro Max search: {exc}"}

        if proc.returncode != 0:
            return {
                "found": False,
                "error": proc.stderr.strip() or proc.stdout.strip() or f"Search exited with code {proc.returncode}.",
            }

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"found": False, "error": f"Unparseable search output:\n{proc.stdout[:2000]}"}

        if design_system:
            ds = payload.get("design_system")
            if ds is None:
                return {"found": False, "error": "Design-system generation returned no result."}
            text = str(ds.get("reasoning") or ds.get("text") or json.dumps(ds, ensure_ascii=False))
            return {"found": True, "design_system": ds, "text": text, "skill_dir": str(script.parent)}

        count = payload.get("count", 0)
        base: Dict[str, Any] = {
            "found": count > 0,
            "count": count,
            "query": payload.get("query", query),
            "domain": payload.get("domain"),
            "stack": payload.get("stack"),
            "results": payload.get("results", []),
            "source": payload.get("file"),
            "skill_dir": str(script.parent),
        }
        if payload.get("redirect"):
            base["redirect"] = payload["redirect"]
        if payload.get("suggestions"):
            base["suggestions"] = payload["suggestions"]
        if count == 0 and not base.get("error"):
            base["note"] = (
                "No database match found for this query. Retry with broader or "
                "different keywords before falling back to generic defaults."
            )
        return base


__all__ = ["SearchUIDesignTool"]