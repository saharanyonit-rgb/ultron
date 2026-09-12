"""Tool base: every V1 tool declares explicit input/output schemas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class ToolError(Exception):
    """Base exception for tool-related errors."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found in the registry."""


class ToolAlreadyExistsError(ToolError):
    """Raised when registering a tool whose name is already registered."""


class InvalidToolError(ToolError):
    """Raised when a tool definition is invalid."""


class InvalidParametersError(ToolError):
    """Raised when tool parameters fail validation."""


class PermissionDeniedError(ToolError):
    """Raised when tool execution is denied by security permissions."""


@dataclass(frozen=True)
class ToolSpec:
    """The machine-readable declaration of a tool, handed to the model layer."""

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema (object)
    output_schema: Dict[str, Any]  # JSON Schema (object)


class Tool(ABC):
    """A single capability the assistant can invoke.

    - `mutates` marks whether executing it changes system state. Every
      mutating call is audit-logged by the agent loop.
    - `run()` must be side-effect-isolated: return a JSON-serializable dict
      describing what happened (including errors as `{"error": ...}`).
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    mutates: bool = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            output_schema=self.output_schema,
        )

    def validate_parameters(self, kwargs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input parameters against the tool's parameter schema.

        Returns (is_valid, error_message).
        """
        required = self.parameters.get("required", [])
        for req in required:
            if req not in kwargs or kwargs[req] is None:
                return False, f"Missing required parameter: '{req}'"

        properties = self.parameters.get("properties", {})
        type_map = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "number": (int, float),
            "array": list,
            "object": dict,
        }

        for param_name, val in kwargs.items():
            if param_name in properties:
                expected_type_str = properties[param_name].get("type")
                if expected_type_str in type_map:
                    expected_cls = type_map[expected_type_str]
                    if expected_cls is int and isinstance(val, bool):
                        return False, f"Parameter '{param_name}' must be of type integer, got bool"
                    if not isinstance(val, expected_cls):
                        return False, f"Parameter '{param_name}' must be of type {expected_type_str}, got {type(val).__name__}"

        return True, None

    @abstractmethod
    def run(self, **kwargs: Any) -> Dict[str, Any]: ...


__all__ = [
    "Tool",
    "ToolSpec",
    "ToolError",
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "InvalidToolError",
    "InvalidParametersError",
    "PermissionDeniedError",
]
