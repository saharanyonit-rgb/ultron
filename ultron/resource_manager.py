"""Resource and Budget Management for JARVIS Phase 5.

Tracks and enforces resource limits: API call budgets, execution time,
token usage, and cost estimation. Prevents runaway execution.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.resource_manager")


class ResourceType(str, Enum):
    API_CALLS = "api_calls"
    TOKENS = "tokens"
    TIME_SECONDS = "time_seconds"
    COST = "cost"


@dataclass
class BudgetConfig:
    """Budget limits for resource consumption."""
    max_api_calls: int = 100
    max_tokens: int = 100000
    max_time_seconds: float = 600.0
    max_cost_usd: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_api_calls": self.max_api_calls,
            "max_tokens": self.max_tokens,
            "max_time_seconds": self.max_time_seconds,
            "max_cost_usd": self.max_cost_usd,
        }


@dataclass
class ResourceUsage:
    """Current resource consumption."""
    api_calls: int = 0
    tokens: int = 0
    time_seconds: float = 0.0
    cost_usd: float = 0.0
    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_calls": self.api_calls,
            "tokens": self.tokens,
            "time_seconds": self.time_seconds,
            "cost_usd": self.cost_usd,
        }


@dataclass
class BudgetExceeded(Exception):
    """Raised when a budget limit is exceeded."""
    resource: str = ""
    limit: float = 0.0
    current: float = 0.0


class ResourceManager:
    """Tracks and enforces resource budgets for autonomous execution.

    Provides:
    - Budget configuration per goal or session
    - Real-time usage tracking
    - Pre-flight checks before actions
    - Cost estimation for LLM calls
    """

    def __init__(self, config: Optional[BudgetConfig] = None) -> None:
        self._config = config or BudgetConfig()
        self._usage = ResourceUsage()
        self._checkpoints: List[Dict[str, Any]] = []
        self._warnings: List[str] = []

    @property
    def config(self) -> BudgetConfig:
        return self._config

    @property
    def usage(self) -> ResourceUsage:
        return self._usage

    def record_api_call(self, tokens: int = 0, cost_usd: float = 0.0) -> None:
        """Record an API call and update usage."""
        self._usage.api_calls += 1
        self._usage.tokens += tokens
        self._usage.cost_usd += cost_usd
        self._check_usage()

    def record_time(self, seconds: float) -> None:
        """Record time consumption."""
        self._usage.time_seconds += seconds
        self._check_usage()

    def check_can_proceed(self) -> bool:
        """Check if we have budget to proceed with another action."""
        return (
            self._usage.api_calls < self._config.max_api_calls
            and self._usage.tokens < self._config.max_tokens
            and self._usage.time_seconds < self._config.max_time_seconds
            and self._usage.cost_usd < self._config.max_cost_usd
        )

    def estimate_llm_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
    ) -> float:
        """Estimate cost of an LLM call."""
        rates = {
            "default": {"input": 0.001, "output": 0.002},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5": {"input": 0.001, "output": 0.002},
        }
        rate = rates.get(model, rates["default"])
        return (input_tokens * rate["input"] + output_tokens * rate["output"]) / 1000

    def get_remaining_budget(self) -> Dict[str, float]:
        """Get remaining budget for each resource type."""
        return {
            ResourceType.API_CALLS.value: max(
                0, self._config.max_api_calls - self._usage.api_calls
            ),
            ResourceType.TOKENS.value: max(
                0, self._config.max_tokens - self._usage.tokens
            ),
            ResourceType.TIME_SECONDS.value: max(
                0, self._config.max_time_seconds - self._usage.time_seconds
            ),
            ResourceType.COST.value: max(
                0, self._config.max_cost_usd - self._usage.cost_usd,
            ),
        }

    def get_usage_percentage(self) -> Dict[str, float]:
        """Get usage as percentage of limits."""
        return {
            ResourceType.API_CALLS.value: (
                self._usage.api_calls / self._config.max_api_calls * 100
                if self._config.max_api_calls > 0 else 0
            ),
            ResourceType.TOKENS.value: (
                self._usage.tokens / self._config.max_tokens * 100
                if self._config.max_tokens > 0 else 0
            ),
            ResourceType.TIME_SECONDS.value: (
                self._usage.time_seconds / self._config.max_time_seconds * 100
                if self._config.max_time_seconds > 0 else 0
            ),
            ResourceType.COST.value: (
                self._usage.cost_usd / self._config.max_cost_usd * 100
                if self._config.max_cost_usd > 0 else 0
            ),
        }

    def checkpoint(self, label: str = "") -> Dict[str, Any]:
        """Take a usage checkpoint."""
        cp = {
            "label": label or f"checkpoint_{len(self._checkpoints)}",
            "usage": self._usage.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._checkpoints.append(cp)
        return cp

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        return list(self._checkpoints)

    def get_warnings(self) -> List[str]:
        return list(self._warnings)

    def reset(self) -> None:
        """Reset all usage tracking."""
        self._usage = ResourceUsage()
        self._checkpoints.clear()
        self._warnings.clear()

    def _check_usage(self) -> None:
        """Check if any limits are being approached."""
        pct = self.get_usage_percentage()

        for resource, usage_pct in pct.items():
            if usage_pct >= 90:
                self._warnings.append(
                    f"BUDGET WARNING: {resource} at {usage_pct:.0f}%"
                )
                logger.warning("Budget %s at %.0f%%", resource, usage_pct)

            if usage_pct >= 100:
                self._warnings.append(
                    f"BUDGET EXCEEDED: {resource}"
                )
                logger.error("Budget exceeded: %s", resource)


__all__ = [
    "ResourceType",
    "BudgetConfig",
    "ResourceUsage",
    "BudgetExceeded",
    "ResourceManager",
]
