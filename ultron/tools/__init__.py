"""Tool registry — the single place V1 capabilities are collected.

Tools are auto-discovered from `ultron.tools.*` modules via the catalog.
No manual list is maintained here.
"""

from __future__ import annotations

# Re-export error hierarchy from central module
from ultron.errors import (  # noqa: F401
    JarvisError,
    ToolExecutionError,
    VerificationError,
)
from ultron.tools.base import (
    InvalidParametersError,
    InvalidToolError,
    PermissionDeniedError,
    Tool,
    ToolAlreadyExistsError,
    ToolError,
    ToolNotFoundError,
    ToolSpec,
)
from ultron.tools.browser_tools import get_browser_tools
from ultron.tools.catalog import default_catalog, default_tools, discover_tools
from ultron.tools.execution import ToolExecutionResult, ToolExecutionStatus, ToolExecutor


def __getattr__(name: str):
    """Lazily resolve `ALL_TOOLS` via auto-discovery (PEP 562).

    The eager module-level list is gone: tools are now discovered from
    `ultron.tools.*` by `ultron.tools.catalog`. This shim keeps existing callers
    working without reintroducing a hand-maintained list — the value is computed
    on first access and then served from the catalog's cache.
    """
    if name == "ALL_TOOLS":
        return default_tools()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ToolRegistry:
    """Authoritative registry for discovering, registering, and retrieving tools."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools if tools is not None else default_tools():
            self.register(t)

    def register(self, tool: Tool, allow_overwrite: bool = False) -> None:
        """Register a new tool instance in the registry."""
        if (
            not hasattr(tool, "name")
            or not str(getattr(tool, "name", "")).strip()
            or not callable(getattr(tool, "run", None))
        ):
            raise InvalidToolError(
                "Cannot register invalid tool: must have a non-empty name and a callable run method."
            )
        name = str(tool.name).strip()
        if name in self._tools and not allow_overwrite:
            raise ToolAlreadyExistsError(f"Tool '{name}' is already registered.")
        self._tools[name] = tool

    def unregister(self, name: str) -> Tool | None:
        """Remove a tool from the registry by name."""
        return self._tools.pop(name, None)

    def exists(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get(self, name: str) -> Tool | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        """Return a list of all registered tools."""
        return list(self._tools.values())

    def specs(self) -> list[ToolSpec]:
        """Return specs for all registered tools."""
        return [t.spec for t in self._tools.values()]


__all__ = [
    "Tool",
    "ToolSpec",
    "ToolRegistry",
    "ToolExecutor",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "discover_tools",
    "default_catalog",
    "default_tools",
    "ToolError",
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "InvalidToolError",
    "InvalidParametersError",
    "PermissionDeniedError",
    "get_browser_tools",
]
