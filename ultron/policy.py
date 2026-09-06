"""Advanced permission policy engine for JARVIS Phase 4.

Extends Phase 2's permission confirmation with risk-based policies.

Policies:
  ALLOW   - Execute without confirmation
  CONFIRM - Require user confirmation
  DENY    - Block execution entirely

The policy engine maps risk levels to actions. For example:
  READ    → ALLOW
  LOW     → ALLOW
  MEDIUM  → CONFIRM
  HIGH    → CONFIRM
  CRITICAL → DENY (or CONFIRM with explicit override)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ultron.risk import RiskLevel

logger = logging.getLogger("ultron.policy")


class PolicyAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


# Default policy: maps risk levels to actions
DEFAULT_POLICY: dict[RiskLevel, PolicyAction] = {
    RiskLevel.READ: PolicyAction.ALLOW,
    RiskLevel.LOW: PolicyAction.ALLOW,
    RiskLevel.MEDIUM: PolicyAction.CONFIRM,
    RiskLevel.HIGH: PolicyAction.CONFIRM,
    RiskLevel.CRITICAL: PolicyAction.DENY,
}


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""

    action: PolicyAction
    risk_level: RiskLevel
    tool_name: str
    reason: str = ""
    overrides: list[str] = field(default_factory=list)


class PolicyEngine:
    """Evaluates tool requests against risk-based policies."""

    def __init__(
        self,
        policy: dict[RiskLevel, PolicyAction] | None = None,
        confirm_callback: Callable[[str, dict, RiskLevel], bool] | None = None,
        tool_overrides: dict[str, PolicyAction] | None = None,
    ) -> None:
        self._policy = dict(DEFAULT_POLICY)
        if policy:
            self._policy.update(policy)
        self._confirm_callback = confirm_callback
        self._tool_overrides = tool_overrides or {}

    def evaluate(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        arguments: dict | None = None,
    ) -> PolicyDecision:
        """Evaluate whether a tool request should be allowed."""
        # Check for tool-specific overrides first
        if tool_name in self._tool_overrides:
            action = self._tool_overrides[tool_name]
            return PolicyDecision(
                action=action,
                risk_level=risk_level,
                tool_name=tool_name,
                reason=f"Tool-specific override: {action.value}",
                overrides=["tool_override"],
            )

        # Use risk-level policy
        action = self._policy.get(risk_level, PolicyAction.CONFIRM)

        return PolicyDecision(
            action=action,
            risk_level=risk_level,
            tool_name=tool_name,
            reason=f"Risk level {risk_level.value} maps to {action.value}",
        )

    def request_permission(
        self,
        tool_name: str,
        risk_level: RiskLevel,
        arguments: dict | None = None,
    ) -> bool:
        """Request permission for a tool operation. Returns True if allowed."""
        decision = self.evaluate(tool_name, risk_level, arguments)

        if decision.action == PolicyAction.ALLOW:
            logger.info("Policy ALLOW: %s (risk=%s)", tool_name, risk_level.value)
            return True

        if decision.action == PolicyAction.DENY:
            logger.warning("Policy DENY: %s (risk=%s)", tool_name, risk_level.value)
            return False

        # CONFIRM: ask the user
        if self._confirm_callback:
            allowed = self._confirm_callback(tool_name, arguments or {}, risk_level)
            logger.info(
                "Policy CONFIRM: %s (risk=%s) → %s",
                tool_name,
                risk_level.value,
                "allowed" if allowed else "denied",
            )
            return allowed

        # No callback configured, deny by default for safety
        logger.warning("Policy CONFIRM but no callback: %s (risk=%s)", tool_name, risk_level.value)
        return False

    def set_tool_override(self, tool_name: str, action: PolicyAction) -> None:
        """Set a policy override for a specific tool."""
        self._tool_overrides[tool_name] = action

    def set_policy(self, risk_level: RiskLevel, action: PolicyAction) -> None:
        """Update the policy for a risk level."""
        self._policy[risk_level] = action

    def get_policy(self) -> dict[RiskLevel, PolicyAction]:
        """Return the current policy."""
        return dict(self._policy)


__all__ = ["PolicyAction", "PolicyDecision", "PolicyEngine", "DEFAULT_POLICY"]
