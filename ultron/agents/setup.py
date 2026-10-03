"""Agent Setup Module - Creates specialized agents with best free OpenRouter models.

This module provides a simple way to instantiate all specialized JARVIS brains
with their optimal free OpenRouter models configured in .env.

Usage:
    from ultron.agents.setup import create_all_agents, get_agent

    agents = create_all_agents()
    coding_agent = agents["coding"]
    result = coding_agent.run("Fix the bug in user_auth.py")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

from ultron.brains import (
    CodingBrain,
    ComputerBrain,
    PlanningBrain,
    ResearchBrain,
    VerificationBrain,
)
from ultron.brains.orchestrator import BrainOrchestrator
from ultron.brains.provider import BrainProviderFactory
from ultron.brains.router import BrainRouter
from ultron.config import BrainConfig, Config, load_config
from ultron.llm.base import LLMProvider
from ultron.tools import Tool, default_tools

logger = logging.getLogger("ultron.agents.setup")


@dataclass
class AgentBundle:
    """Container for all specialized agents and orchestration components."""

    planning: PlanningBrain
    research: ResearchBrain
    coding: CodingBrain
    computer: ComputerBrain
    verification: VerificationBrain
    router: BrainRouter
    orchestrator: BrainOrchestrator
    provider_factory: BrainProviderFactory
    config: Config


def create_providers(config: Config) -> dict[str, LLMProvider]:
    """Create LLM providers for each brain type using configured free models.

    Returns a dict mapping brain type to its provider.
    """
    factory = BrainProviderFactory(config.llm)

    # Config.brain is always materialised as a BrainConfig by Config.__init__.
    brain = cast(BrainConfig, config.brain)
    brain_configs = {
        "planning": brain.planning,
        "research": brain.research,
        "coding": brain.coding,
        "computer": brain.computer,
        "verification": brain.verification,
        "fast": brain.fast,
    }

    providers = {}
    for brain_type, model_config in brain_configs.items():
        try:
            provider = factory.create_provider(model_config)
            providers[brain_type] = provider
            logger.info(
                "Created provider for %s: %s (%s)",
                brain_type,
                model_config.model,
                model_config.provider,
            )
        except Exception as e:
            logger.error("Failed to create provider for %s: %s", brain_type, e)
            raise

    return providers


def create_brains(
    providers: dict[str, LLMProvider],
    tools: list[Tool],
    tool_executor: Any | None = None,
) -> dict[str, Any]:
    """Create all specialized brain agents with their providers.

    Returns a dict mapping brain type to brain instance.
    """
    brains: dict[str, Any] = {}

    brains["planning"] = PlanningBrain(
        provider=providers["planning"],
        tools=tools,
    )

    brains["research"] = ResearchBrain(
        provider=providers["research"],
        tools=tools,
        tool_executor=tool_executor,
    )

    brains["coding"] = CodingBrain(
        provider=providers["coding"],
        tools=tools,
        tool_executor=tool_executor,
    )

    brains["computer"] = ComputerBrain(
        provider=providers["computer"],
        tools=tools,
        tool_executor=tool_executor,
    )

    brains["verification"] = VerificationBrain(
        provider=providers["verification"],
        tools=tools,
    )

    return brains


def create_all_agents(
    config: Config | None = None,
    tools: list[Tool] | None = None,
    tool_executor: Any | None = None,
) -> AgentBundle:
    """Create all specialized agents with best free OpenRouter models.

    This is the main entry point. It loads config, creates providers,
    instantiates all brains, and returns a complete bundle.

    Args:
        config: Optional pre-loaded Config. If None, loads from .env
        tools: Optional list of tools. If None, tools are auto-discovered
        tool_executor: Optional tool executor for security enforcement

    Returns:
        AgentBundle with all agents ready to use

    Example:
        bundle = create_all_agents()
        result = bundle.coding.run("Create a REST API for user management")
        plan = bundle.planning.plan("Build a todo app with React")
    """
    if config is None:
        config = load_config()

    if tools is None:
        tools = default_tools()

    logger.info("Creating providers with free OpenRouter models...")
    providers = create_providers(config)

    logger.info("Creating specialized brain agents...")
    brains = create_brains(providers, tools, tool_executor)

    logger.info("Creating router and orchestrator...")
    router = BrainRouter()
    orchestrator = BrainOrchestrator(
        config=config,
        tools=tools,
        tool_executor=tool_executor,
    )

    factory = BrainProviderFactory(config.llm)

    logger.info("All agents created successfully!")

    return AgentBundle(
        planning=brains["planning"],
        research=brains["research"],
        coding=brains["coding"],
        computer=brains["computer"],
        verification=brains["verification"],
        router=router,
        orchestrator=orchestrator,
        provider_factory=factory,
        config=config,
    )


def get_agent(bundle: AgentBundle, brain_type: str) -> Any:
    """Get a specific agent from the bundle.

    Args:
        bundle: The AgentBundle from create_all_agents()
        brain_type: One of "planning", "research", "coding", "computer", "verification", "fast"

    Returns:
        The requested brain agent
    """
    agent_map = {
        "planning": bundle.planning,
        "research": bundle.research,
        "coding": bundle.coding,
        "computer": bundle.computer,
        "verification": bundle.verification,
        "fast": bundle.research,  # Fast uses research brain (lightning model)
    }

    if brain_type not in agent_map:
        raise ValueError(f"Unknown brain type: {brain_type}. Available: {list(agent_map.keys())}")

    return agent_map[brain_type]


def route_and_execute(
    bundle: AgentBundle,
    user_input: str,
    context: dict[str, Any] | None = None,
) -> Any:
    """Route a request to the appropriate brain and execute it.

    This is a convenience function that uses the router to select
    the best brain and then executes the task.

    Args:
        bundle: The AgentBundle from create_all_agents()
        user_input: The user's request
        context: Optional context dict

    Returns:
        The result from the selected brain
    """
    route_decision = bundle.router.route(user_input, context)
    brain_type = route_decision.brain_type.value

    logger.info(
        "Routing to %s brain (confidence: %.2f): %s",
        brain_type,
        route_decision.confidence,
        route_decision.reasoning,
    )

    # Map brain types to available agents
    if brain_type == "fast":
        brain_type = "research"  # Fast uses research brain
    elif brain_type == "general":
        brain_type = "research"  # General uses research brain

    brain = get_agent(bundle, brain_type)

    if brain_type == "planning":
        return brain.plan(user_input, context)
    elif brain_type == "research":
        return brain.research(user_input, context)
    elif brain_type == "coding":
        return brain.execute(user_text=user_input, context=context)
    elif brain_type == "computer":
        return brain.execute(user_text=user_input, context=context)
    elif brain_type == "verification":
        if not context:
            raise ValueError("Verification requires context")
        return brain.verify(
            task_description=context.get("task", user_input),
            expected_outcome=context.get("expected_outcome", ""),
            actual_result=context.get("actual_result", ""),
            evidence=context.get("evidence", []),
        )
    else:
        return brain.research(user_input, context)


def print_model_summary(config: Config) -> None:
    """Print a summary of the models configured for each brain."""
    print("\n" + "=" * 70)
    print("JARVIS SPECIALIZED BRAINS - FREE OPENROUTER MODELS")
    print("=" * 70)

    brain = cast(BrainConfig, config.brain)
    brains = {
        "Planning": brain.planning,
        "Research": brain.research,
        "Coding": brain.coding,
        "Computer": brain.computer,
        "Verification": brain.verification,
        "Fast": brain.fast,
    }

    for name, model_config in brains.items():
        print(f"\n{name} Brain:")
        print(f"  Model:      {model_config.model}")
        print(f"  Provider:   {model_config.provider}")
        print(f"  Temperature: {model_config.temperature}")
        print(f"  Max Tokens: {model_config.max_tokens:,}")

    print("\n" + "=" * 70)
    print("All models are FREE tier on OpenRouter")
    print("=" * 70 + "\n")


__all__ = [
    "AgentBundle",
    "create_all_agents",
    "create_providers",
    "create_brains",
    "get_agent",
    "route_and_execute",
    "print_model_summary",
]
