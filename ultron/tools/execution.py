"""Tool Executor — safe execution boundary for JARVIS tools.

Handles:
- Tool lookup in ToolRegistry
- Parameter validation against tool schemas
- Security permission checks via PermissionGate
- Safe execution isolation and audit logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from ultron.actions import PermissionDecision, PermissionGate
from ultron.tools.base import Tool

if TYPE_CHECKING:
    from ultron.actions.audit_log import AuditLog
    from ultron.tools import ToolRegistry

logger = logging.getLogger("ultron.tools.executor")


class ToolExecutionStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PERMISSION_DENIED = "permission_denied"


@dataclass(frozen=True)
class ToolExecutionResult:
    """Structured result returned by the ToolExecutor."""

    tool_name: str
    status: ToolExecutionStatus
    output: Dict[str, Any]
    allowed: bool = True
    error: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """Executes tools safely through validation, permission checks, and audit logging."""

    def __init__(
        self,
        registry: "ToolRegistry",
        gate: Optional[PermissionGate] = None,
        audit_log: Optional["AuditLog"] = None,
    ) -> None:
        self._registry = registry
        self._gate = gate or PermissionGate()
        self._audit = audit_log

    @property
    def registry(self) -> "ToolRegistry":
        return self._registry

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """Safely validate and execute a tool by name."""
        arguments = dict(arguments or {})

        # 1. Tool Lookup
        tool = self._registry.get(tool_name)
        if tool is None:
            err_msg = f"unknown tool: {tool_name}"
            logger.warning("Tool execution failed: %s", err_msg)
            output = {"error": err_msg}
            decision = PermissionDecision(allowed=False, reason="unknown tool")
            if self._audit:
                self._audit.record(tool_name, arguments, output, decision)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILURE,
                output=output,
                allowed=False,
                error="unknown tool",
                arguments=arguments,
            )

        # 2. Parameter Validation
        if hasattr(tool, "validate_parameters") and callable(getattr(tool, "validate_parameters", None)):
            is_valid, validation_err = tool.validate_parameters(arguments)
        else:
            is_valid, validation_err = True, None

        if not is_valid:
            err_msg = f"Invalid parameters for tool '{tool_name}': {validation_err}"
            logger.warning("Tool parameter validation failed: %s", err_msg)
            output = {"error": err_msg}
            decision = PermissionDecision(allowed=True, reason="parameter validation failed")
            if self._audit:
                self._audit.record(tool_name, arguments, output, decision)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.FAILURE,
                output=output,
                allowed=True,
                error=validation_err,
                arguments=arguments,
            )

        # 3. Security Permission Check
        decision = self._gate.check(tool, arguments)
        if not decision.allowed:
            logger.warning("Tool execution permission denied for '%s': %s", tool_name, decision.reason)
            output = {"error": decision.reason}
            if self._audit:
                self._audit.record(tool_name, arguments, output, decision)
            return ToolExecutionResult(
                tool_name=tool_name,
                status=ToolExecutionStatus.PERMISSION_DENIED,
                output=output,
                allowed=False,
                error=decision.reason,
                arguments=arguments,
            )

        # 4. Safe Tool Execution
        try:
            output = tool.run(**arguments)
            if not isinstance(output, dict):
                output = {"result": output}
            status = ToolExecutionStatus.FAILURE if "error" in output else ToolExecutionStatus.SUCCESS
            error_str = str(output["error"]) if "error" in output else None
        except Exception as exc:
            err_type = type(exc).__name__
            output = {"error": f"{err_type}: {exc}"}
            status = ToolExecutionStatus.FAILURE
            error_str = f"{err_type}: {exc}"

        if self._audit:
            self._audit.record(tool_name, arguments, output, decision)

        return ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            output=output,
            allowed=True,
            error=error_str,
            arguments=arguments,
        )


__all__ = [
    "ToolExecutor",
    "ToolExecutionResult",
    "ToolExecutionStatus",
]
