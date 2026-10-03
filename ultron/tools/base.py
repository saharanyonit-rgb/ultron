"""Tool base: every V1 tool declares explicit input/output schemas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ultron.risk import RiskLevel


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
    """The machine-readable declaration of a tool, handed to the model layer.

    This is the single representation of a tool that every consumer reads.
    Routing keywords, risk classification and audit behaviour are all derived
    from the owning `Tool` class rather than from side tables, so a tool can
    never be registered-but-unreachable or registered-but-mis-classified.
    """

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (object)
    output_schema: dict[str, Any]  # JSON Schema (object)
    category: str = ""
    risk: RiskLevel = RiskLevel.MEDIUM
    mutates: bool = False


class Tool(ABC):
    """A single capability the assistant can invoke.

    Metadata declared here is authoritative. Nothing else in the codebase is
    allowed to keep a parallel list of tool names:

    - `mutates` marks whether executing it changes system state. Every
      mutating call is audit-logged by the agent loop.
    - `risk` is the permission-engine classification. It has no permissive
      default: `ultron.tools.catalog` refuses to register a tool that leaves
      it unset, because an unclassified tool is a security hole, not a default.
    - `category` groups related tools. When left unset it is derived from the
      defining module, so most tools never need to spell it out.
    - `keywords` are extra phrases that make deterministic intent routing
      precise. They extend the phrases auto-derived from the tool's name,
      description and category rather than replacing them, so a tool is
      routable even if it declares none.
    - `run()` must be side-effect-isolated: return a JSON-serializable dict
      describing what happened (including errors as `{"error": ...}`).
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    mutates: bool = False
    risk: RiskLevel | None = None
    category: str = ""
    keywords: tuple[str, ...] = ()

    @property
    def effective_category(self) -> str:
        """The tool's category, derived from its module when not declared."""
        if self.category:
            return self.category
        module = type(self).__module__.rsplit(".", 1)[-1]
        # Strip repeatedly: `file_ops_unrestricted` -> `file_ops` -> `file`.
        # Order matters, the longest/most specific suffix must be tried first.
        for suffix in ("_unrestricted", "_tools", "_tool", "_ops", "_control"):
            if module.endswith(suffix) and module != suffix:
                module = module[: -len(suffix)]
                break
        return module or "general"

    @property
    def effective_risk(self) -> RiskLevel:
        """The tool's risk level, falling back to the most conservative one.

        The catalog rejects undeclared risk at registration time, so this
        fallback only applies to hand-built specs outside a registry.
        """
        return self.risk or RiskLevel.HIGH

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            output_schema=self.output_schema,
            category=self.effective_category,
            risk=self.effective_risk,
            mutates=self.mutates,
        )

    def validate_parameters(self, kwargs: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate input parameters against the tool's parameter schema.

        Returns (is_valid, error_message).
        """
        required = self.parameters.get("required", [])
        for req in required:
            if req not in kwargs or kwargs[req] is None:
                return False, f"Missing required parameter: '{req}'"

        properties = self.parameters.get("properties", {})
        type_map: dict[str, Any] = {
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
                        return (
                            False,
                            f"Parameter '{param_name}' must be of type {expected_type_str}, got {type(val).__name__}",
                        )

        return True, None

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool.

        Concrete tools narrow this to their own named parameters (e.g.
        ``run(self, url: str, **kwargs)``) so callers get real signatures and
        IDE completion, but every call site in the codebase invokes
        ``tool.run(**validated_arguments)``. Declaring ``*args`` here keeps
        those narrowed overrides type-compatible with the base class instead
        of forcing each one to be annotated as a Liskov violation.
        """
        ...


__all__ = [
    "Tool",
    "ToolSpec",
    "RiskLevel",
    "ToolError",
    "ToolNotFoundError",
    "ToolAlreadyExistsError",
    "InvalidToolError",
    "InvalidParametersError",
    "PermissionDeniedError",
]
