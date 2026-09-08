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

from enum import Enum


class RiskLevel(str, Enum):
    READ = "read"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Default risk classifications for known tool categories
DEFAULT_RISK_MAP: dict[str, RiskLevel] = {
    # Read-only tools
    "get_system_info": RiskLevel.READ,
    "get_clipboard": RiskLevel.READ,
    "search_files": RiskLevel.READ,
    "read_file": RiskLevel.READ,
    "open_url": RiskLevel.READ,
    "take_screenshot": RiskLevel.READ,
    # Low-risk mutations
    "set_clipboard": RiskLevel.LOW,
    "open_app": RiskLevel.LOW,
    # Medium-risk mutations
    "create_file": RiskLevel.MEDIUM,
    "close_app": RiskLevel.MEDIUM,
    # High-risk mutations
    "delete_file": RiskLevel.HIGH,
    "move_file": RiskLevel.HIGH,
    "rename_file": RiskLevel.HIGH,
    # Critical operations
    "execute_command": RiskLevel.CRITICAL,
    "execute_shell": RiskLevel.CRITICAL,
    "windows_shutdown": RiskLevel.CRITICAL,
}


class RiskClassifier:
    """Classifies tool operations by risk level."""

    def __init__(self, custom_risk_map: dict[str, RiskLevel] | None = None) -> None:
        self._risk_map = dict(DEFAULT_RISK_MAP)
        if custom_risk_map:
            self._risk_map.update(custom_risk_map)

    def classify(self, tool_name: str, arguments: dict | None = None) -> RiskLevel:
        """Classify a tool operation by risk level."""
        if tool_name in self._risk_map:
            return self._risk_map[tool_name]
        # Default to MEDIUM for unknown tools
        return RiskLevel.MEDIUM

    def register(self, tool_name: str, risk_level: RiskLevel) -> None:
        """Register a custom risk classification for a tool."""
        self._risk_map[tool_name] = risk_level

    def get_all_classifications(self) -> dict[str, RiskLevel]:
        """Return all registered risk classifications."""
        return dict(self._risk_map)


__all__ = ["RiskLevel", "RiskClassifier", "DEFAULT_RISK_MAP"]
