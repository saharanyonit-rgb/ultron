"""Risk classification system for JARVIS Phase 4.

Every tool operation is classified by risk level. The permission engine
uses these classifications to decide whether to allow, confirm, or deny
an operation.

Risk levels:
  READ    - No side effects, read-only operations
  LOW     - Minor mutations, easily reversible
  MEDIUM  - Significant mutations, may require confirmation
  HIGH    - Destructive operations, always require confirmation
  CRITICAL - System-level operations, require explicit authorization
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ultron.tools.catalog import ToolCatalog


class RiskLevel(StrEnum):
    READ = "read"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskClassifier:
    """Classifies tool operations by risk level.

    Risk is derived from the tool's own `risk` declaration in its metadata.
    No hardcoded side-tables are used — the catalog is the single source of truth.

    The catalog import is deferred to construction time: `ultron.tools.catalog`
    imports `RiskLevel` from this module, so importing it eagerly would be
    circular.
    """

    def __init__(self, catalog: ToolCatalog | None = None) -> None:
        if catalog is None:
            from ultron.tools.catalog import default_catalog

            catalog = default_catalog()
        self._catalog = catalog
        # Runtime overrides layered on top of the declared risk. Kept separate
        # from the catalog so a caller's decision never mutates tool metadata.
        self._overrides: dict[str, RiskLevel] = {}

    def classify(self, tool_name: str, arguments: dict | None = None) -> RiskLevel:
        """Classify a tool operation by risk level."""
        if tool_name in self._overrides:
            return self._overrides[tool_name]
        risk = self._catalog.risk_of(tool_name)
        if risk is not None:
            return risk
        # Not in the catalog. MEDIUM keeps a per-session downgrade possible
        # without letting an unregistered name default to something permissive.
        return RiskLevel.MEDIUM

    def register(self, tool_name: str, risk_level: RiskLevel) -> None:
        """Override the risk level for `tool_name` for this classifier only.

        The authoritative value is the tool's own `risk` declaration; this is a
        session-scoped override and is not written back to the catalog.
        """
        self._overrides[tool_name] = risk_level

    def clear_overrides(self) -> None:
        """Drop every runtime override, restoring declared risk levels."""
        self._overrides.clear()

    def get_all_classifications(self) -> dict[str, RiskLevel]:
        """Return every known classification: declared risk plus overrides."""
        return {**self._catalog.risk_map(), **self._overrides}


__all__ = ["RiskLevel", "RiskClassifier"]
