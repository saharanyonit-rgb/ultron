"""Tool catalog — the single source of truth for tool discovery and metadata.

Everything that used to be a hand-maintained side table is derived here from the
`Tool` classes themselves:

  - tool registration      -> :func:`discover_tools` walks the package
  - intent routing         -> phrase/token indexes built from tool metadata
  - risk classification    -> `Tool.risk`, declared on the class

The rules this module enforces:

  1. A new tool becomes available by being defined in `ultron.tools.*`. There is
     no list to append to and no spec file to regenerate.
  2. Every registered tool must declare a `risk` level. An unclassified tool is
     a security hole, so registration fails loudly instead of defaulting to
     something permissive.
  3. Every registered tool is routable. Phrases come from the tool's own name
     and any explicitly declared `keywords`, so a tool cannot be silently
     unreachable the way 53 tools were before.

Platform gating is inferred rather than listed: a tool module that imports
`ultron.tools._termux` is an Android/Termux module and only loads on Android.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import re
from dataclasses import dataclass, field

from ultron.risk import RiskLevel
from ultron.tools.base import InvalidToolError, Tool

logger = logging.getLogger("ultron.tools.catalog")

# Modules that never define a directly-constructible tool.
_NON_TOOL_MODULES = frozenset({"base", "catalog", "command", "execution", "filesystem", "_termux"})

# Factory function a module may expose to build its tools with shared state.
_FACTORY_NAMES = ("get_tools", "get_browser_tools")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Phrase matching is done on a compiled, boundary-anchored regex rather than
# `phrase in text`, so a derived single-word category ("file") cannot fire on
# a substring of a longer word ("profile").
_PHRASE_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _phrase_re(phrase: str) -> re.Pattern[str]:
    compiled = _PHRASE_RE_CACHE.get(phrase)
    if compiled is None:
        parts = [_TOKEN_RE.findall(w) or [re.escape(w)] for w in phrase.split()]
        body = r"\s+".join(r"\b" + r"[\s\-\_]*".join(p) + r"\b" for p in parts)
        compiled = re.compile(body)
        _PHRASE_RE_CACHE[phrase] = compiled
    return compiled

# Words too common to carry routing signal.
_STOPWORDS = frozenset(
    {
        "and", "are", "can", "for", "from", "get", "has", "into", "its", "not", "only",
        "or", "our", "set", "than", "that", "the", "then", "this", "tool", "use", "used",
        "using", "was", "were", "what", "when", "which", "will", "with", "you", "your",
    }
)


def _android_available() -> bool:
    try:
        from ultron.platform import is_android

        return bool(is_android())
    except Exception:
        return False


def _module_is_android_gated(module) -> bool:
    """True when a module delegates to Termux, i.e. it only works on Android.

    Detected from imported symbols' ``__module__`` (``run_termux`` is a
    function whose own ``__name__`` is just ``run_termux``).
    """
    return any(
        getattr(obj, "__module__", "") == "ultron.tools._termux" for obj in vars(module).values()
    )


def _tool_classes_in(module) -> list[type[Tool]]:
    return [
        obj
        for obj in vars(module).values()
        if inspect.isclass(obj)
        and issubclass(obj, Tool)
        and obj is not Tool
        and obj.__module__ == module.__name__
    ]


def _instantiate_module(module) -> list[Tool]:
    """Build the tool instances a module contributes."""
    for factory_name in _FACTORY_NAMES:
        factory = getattr(module, factory_name, None)
        if callable(factory):
            built = [t for t in factory() if isinstance(t, Tool)]
            if built:
                return built

    tools: list[Tool] = []
    for cls in _tool_classes_in(module):
        try:
            tools.append(cls())
        except TypeError as exc:
            # A tool needing constructor wiring must expose a factory.
            logger.warning(
                "Tool %s.%s is not directly constructible and has no factory: %s",
                module.__name__,
                cls.__name__,
                exc,
            )
    return tools


def discover_tools() -> list[Tool]:
    """Import every tool module and return the tool instances they provide.

    Returns:
        Tools in a deterministic order, de-duplicated by name.
    """
    package = importlib.import_module("ultron.tools")
    android = _android_available()

    discovered: dict[str, Tool] = {}
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if info.ispkg or info.name in _NON_TOOL_MODULES:
            continue
        try:
            module = importlib.import_module(f"{package.__name__}.{info.name}")
        except Exception as exc:
            logger.warning("Skipping tool module %s: %s", info.name, exc)
            continue

        if _module_is_android_gated(module) and not android:
            logger.debug("Skipping Android-only tool module %s", info.name)
            continue

        for tool in _instantiate_module(module):
            existing = discovered.get(tool.name)
            if existing is not None:
                if type(existing) is type(tool):
                    continue
                raise InvalidToolError(
                    f"Duplicate tool name '{tool.name}': "
                    f"{type(existing).__module__}.{type(existing).__name__} and "
                    f"{type(tool).__module__}.{type(tool).__name__} both claim it. "
                    "Tool names must be unique."
                )
            discovered[tool.name] = tool

    return list(discovered.values())


@dataclass(frozen=True)
class ToolMetadata:
    """Routing and policy metadata derived from one tool."""

    name: str
    category: str
    risk: RiskLevel
    mutates: bool
    phrases: tuple[str, ...]  # high-confidence routing phrases
    tokens: frozenset[str]  # scoring tokens for the fallback matcher

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "category": self.category,
            "risk": self.risk.value,
            "mutates": self.mutates,
            "phrases": list(self.phrases),
        }


def _phrases_for(tool: Tool) -> tuple[str, ...]:
    """Routing phrases: the tool's own name plus any declared keywords."""
    phrases = {
        tool.name.lower(),
        tool.name.lower().replace("_", " "),
        tool.effective_category.lower(),
    }
    for keyword in tool.keywords:
        cleaned = keyword.strip().lower()
        if cleaned:
            phrases.add(cleaned)
    return tuple(sorted(p for p in phrases if len(p) >= 2))


def _tokens_for(tool: Tool) -> frozenset[str]:
    """Scoring tokens from name, category and description."""
    tokens = {
        t
        for t in _TOKEN_RE.findall(f"{tool.name.replace('_', ' ')} {tool.effective_category}")
        if len(t) >= 3
    }
    tokens.update(
        t for t in _TOKEN_RE.findall(tool.description.lower()) if len(t) >= 4 and t not in _STOPWORDS
    )
    return frozenset(tokens)


def build_metadata(tool: Tool) -> ToolMetadata:
    if tool.risk is None:
        raise InvalidToolError(
            f"Tool '{tool.name}' ({type(tool).__module__}.{type(tool).__name__}) does not "
            "declare a 'risk' level. Every tool must declare one, e.g. "
            "`risk = RiskLevel.MEDIUM`."
        )
    if tool.risk == RiskLevel.READ and tool.mutates:
        # A tool cannot both be side-effect-free and change state. This pairing
        # used to slip through on open_url/take_screenshot, which let a
        # mutating call pass a read-only gate.
        raise InvalidToolError(
            f"Tool '{tool.name}' declares risk=READ but mutates=True. A tool that "
            "changes state must declare at least RiskLevel.LOW."
        )
    return ToolMetadata(
        name=tool.name,
        category=tool.effective_category,
        risk=tool.effective_risk,
        mutates=tool.mutates,
        phrases=_phrases_for(tool),
        tokens=_tokens_for(tool),
    )


@dataclass
class ToolCatalog:
    """An indexed, validated view over a set of tools."""

    tools: tuple[Tool, ...]
    metadata: dict[str, ToolMetadata] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metadata:
            self.metadata = {t.name: build_metadata(t) for t in self.tools}

    # ── lookups ──────────────────────────────────────────────
    @property
    def names(self) -> list[str]:
        return [t.name for t in self.tools]

    def get(self, name: str) -> Tool | None:
        return next((t for t in self.tools if t.name == name), None)

    def meta(self, name: str) -> ToolMetadata | None:
        return self.metadata.get(name)

    def risk_of(self, name: str) -> RiskLevel | None:
        meta = self.metadata.get(name)
        return meta.risk if meta else None

    def risk_map(self) -> dict[str, RiskLevel]:
        return {name: meta.risk for name, meta in self.metadata.items()}

    def by_category(self, category: str) -> list[Tool]:
        return [t for t in self.tools if self.metadata[t.name].category == category]

    def categories(self) -> list[str]:
        return sorted({meta.category for meta in self.metadata.values()})

    # ── routing ──────────────────────────────────────────────
    def match_phrases(self, text: str) -> list[tuple[str, str]]:
        """Return `(tool_name, phrase)` for every phrase contained in `text`.

        Matching is word-boundary aware. A raw substring test is wrong for the
        auto-derived phrases: the category `file` would otherwise fire on
        "profile", and `memory` on the brain's memory preamble, routing ordinary
        conversation to a tool.

        Ordered by descending phrase length so the most specific match wins.
        """
        lowered = text.lower()
        hits: list[tuple[str, str]] = []
        for name, meta in self.metadata.items():
            for phrase in meta.phrases:
                if phrase and _phrase_re(phrase).search(lowered):
                    hits.append((name, phrase))
        hits.sort(key=lambda item: len(item[1]), reverse=True)
        return hits

    def best_phrase_match(self, text: str) -> tuple[str, str] | None:
        """The single most specific `(tool_name, phrase)` match, if any."""
        hits = self.match_phrases(text)
        return hits[0] if hits else None

    def score_tokens(self, text: str) -> list[tuple[str, float, int]]:
        """Rank tools by token overlap with `text`.

        Returns `(tool_name, coverage, overlap_count)` per tool with any
        overlap, highest coverage first. `overlap_count` is exposed because
        coverage alone is misleading: in a short sentence one incidental word
        can reach 50% coverage, which is not a real signal. Callers that are
        about to change behaviour on a match should require more than one
        distinct token.
        """
        lowered = _TOKEN_RE.findall(text.lower())
        if not lowered:
            return []
        text_tokens = {t for t in lowered if len(t) >= 3 and t not in _STOPWORDS}
        if not text_tokens:
            return []
        scored: list[tuple[str, float, int]] = []
        for name, meta in self.metadata.items():
            overlap = text_tokens & meta.tokens
            if overlap:
                scored.append((name, len(overlap) / len(text_tokens), len(overlap)))
        scored.sort(key=lambda item: (-item[1], -item[2]))
        return scored


def build_catalog(tools: list[Tool] | None = None) -> ToolCatalog:
    """Validate `tools` and index them. Uses discovery when `tools` is None."""
    resolved = list(tools) if tools is not None else discover_tools()
    return ToolCatalog(tuple(resolved))


_CACHED: ToolCatalog | None = None


def default_catalog(refresh: bool = False) -> ToolCatalog:
    """The process-wide catalog, discovered once and cached."""
    global _CACHED
    if _CACHED is None or refresh:
        _CACHED = build_catalog()
    return _CACHED


def default_tools() -> list[Tool]:
    """The process-wide tool list, discovered once and cached."""
    return list(default_catalog().tools)


__all__ = [
    "ToolCatalog",
    "ToolMetadata",
    "build_catalog",
    "build_metadata",
    "default_catalog",
    "default_tools",
    "discover_tools",
    "RiskLevel",
]
