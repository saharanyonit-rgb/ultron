"""JARVIS Phase 7: Multi-Model Specialized Brain Architecture.

This module provides the specialized brain agents for JARVIS:
- Planning Brain: Goal decomposition and task planning
- Research Brain: Information gathering and analysis
- Coding Brain: Code analysis and implementation
- Computer Brain: Computer control and automation
- Verification Brain: Independent result verification

Plus:
- BrainProviderFactory: Creates LLM providers for brains
- BrainRouter: Selects appropriate brain based on task
- BrainOrchestrator: Orchestrates multi-brain execution

Phase 7.7: Enhanced with CapabilityBasedRouter for intelligent
capability-based routing instead of keyword-based routing.
"""

from __future__ import annotations

from ultron.brains.router import BrainRouter, BrainType, BrainRouteDecision
from ultron.brains.planning import PlanningBrain, ExecutionPlan, PlannedTask
from ultron.brains.research import ResearchBrain, ResearchFinding, ResearchReport
from ultron.brains.coding import CodingBrain, CodeChange, CodingResult
from ultron.brains.computer import ComputerBrain, ComputerAction, ComputerResult
from ultron.brains.verification import (
    VerificationBrain,
    VerificationResult,
    VerificationStatus,
    VerificationRecommendation,
)
from ultron.brains.provider import BrainProviderFactory
from ultron.brains.capability_router import (
    CapabilityBasedRouter,
    BrainCapability,
    BrainCapabilities,
    BrainCapabilityRegistry,
    TaskRequirements,
    RoutingDecision,
    RoutingScore,
    Intent,
    Complexity,
    RiskLevel,
)

def __getattr__(name: str):
    if name == "BrainOrchestrator":
        from ultron.brains.orchestrator import BrainOrchestrator
        return BrainOrchestrator
    if name == "BrainOrchestrationResult":
        from ultron.brains.orchestrator import BrainOrchestrationResult
        return BrainOrchestrationResult
    if name == "BrainOrchestrationEvent":
        from ultron.brains.orchestrator import BrainOrchestrationEvent
        return BrainOrchestrationEvent
    if name == "BrainContext":
        from ultron.brains.orchestrator import BrainContext
        return BrainContext
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "BrainProviderFactory",
    "BrainRouter",
    "BrainType",
    "BrainRouteDecision",
    "PlanningBrain",
    "ExecutionPlan",
    "PlannedTask",
    "ResearchBrain",
    "ResearchFinding",
    "ResearchReport",
    "CodingBrain",
    "CodeChange",
    "CodingResult",
    "ComputerBrain",
    "ComputerAction",
    "ComputerResult",
    "VerificationBrain",
    "VerificationResult",
    "VerificationStatus",
    "VerificationRecommendation",
    "BrainOrchestrator",
    "BrainOrchestrationResult",
    "BrainOrchestrationEvent",
    "BrainContext",
    # Phase 7.7: Capability-based routing
    "CapabilityBasedRouter",
    "BrainCapability",
    "BrainCapabilities",
    "BrainCapabilityRegistry",
    "TaskRequirements",
    "RoutingDecision",
    "RoutingScore",
    "Intent",
    "Complexity",
    "RiskLevel",
]
