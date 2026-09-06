"""Actions package — audit logging and the permission/confirmation layer.

V1 rules:
- Every action the assistant takes is written to an append-only audit log.
- Nothing in V1 is destructive, so the permission gate passes everything
  through. The gate is the explicit extension point where V2 (permissioned
  execution) will ask for confirmation before a mutating action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ultron.tools.base import Tool

# Re-export the error hierarchy for convenience
from ultron.errors import (  # noqa: F401
    AuthenticationError,
    ConfigurationError,
    ExecutionError,
    InvalidParametersError,
    InvalidToolError,
    JarvisError,
    MalformedResponseError,
    ProviderError,
    RateLimitError,
    PermissionDeniedError,
    TimeoutError,
    ToolAlreadyExistsError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    VerificationError,
)


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""


class PermissionGate:
    """Extension point: V1 = unconditional pass-through (nothing destructive).

    V2 will move the mutating branch behind a confirmation prompt (or a
    rules table) without changing the agent loop's contract: check -> decide
    -> record.
    """

    def check(self, tool: "Tool", arguments: dict[str, Any]) -> PermissionDecision:
        if getattr(tool, "mutates", False):
            return PermissionDecision(allowed=True, reason="v1 pass-through (mutating action)")
        return PermissionDecision(allowed=True, reason="read-only action")


__all__ = ["PermissionGate", "PermissionDecision"]
