#!/usr/bin/env python
"""Demo script showing how to use specialized agents with free OpenRouter models."""

from ultron.agents.setup import create_all_agents, print_model_summary, route_and_execute
from ultron.config import load_config


def main():
    print("Loading configuration...")
    config = load_config()
    
    print_model_summary(config)
    
    print("Creating all specialized agents...")
    bundle = create_all_agents(config=config)
    
    print("\nAgents ready!")
    print(f"- Planning:   {bundle.planning.spec.name} (model: {config.brain.planning.model})")
    print(f"- Research:   {bundle.research.spec.name} (model: {config.brain.research.model})")
    print(f"- Coding:     {bundle.coding.spec.name} (model: {config.brain.coding.model})")
    print(f"- Computer:   {bundle.computer.spec.name} (model: {config.brain.computer.model})")
    print(f"- Verification: {bundle.verification.spec.name} (model: {config.brain.verification.model})")
    
    print("\n" + "=" * 70)
    print("EXAMPLE USAGE")
    print("=" * 70)
    
    print("""
# Direct agent usage:
plan = bundle.planning.plan("Build a todo app with React and FastAPI")
report = bundle.research.research("Compare React vs Vue for 2024")
code_result = bundle.coding.execute("Create a user authentication module")
computer_result = bundle.computer.execute("Open browser to github.com")

# Auto-routing (recommended):
result = route_and_execute(bundle, "Research the best Python async frameworks")
result = route_and_execute(bundle, "Plan a microservices architecture")
result = route_and_execute(bundle, "Fix the login bug in auth.py")
result = route_and_execute(bundle, "Open calculator app")

# Full orchestration with verification:
from ultron.brains.orchestrator import BrainContext
context = BrainContext(
    goal="Create a REST API",
    task="Implement user CRUD endpoints",
    expected_outcome="Working FastAPI endpoints with tests",
)
result = bundle.orchestrator.execute("Create a REST API for users", context)
""")
    
    print("=" * 70)
    print("Run with: python demo_agents.py")
    print("=" * 70)


if __name__ == "__main__":
    main()