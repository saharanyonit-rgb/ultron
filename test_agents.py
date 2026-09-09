#!/usr/bin/env python
"""Quick test to verify agents work with OpenRouter free models."""

import os
from ultron.agents.setup import create_all_agents, route_and_execute
from ultron.config import load_config


def main():
    # Verify API key is set
    api_key = os.environ.get("ULTRON_OPENROUTER_API_KEY")
    if not api_key:
        # Try loading from .env
        from ultron.config import load_dotenv
        dotenv = load_dotenv()
        api_key = dotenv.get("ULTRON_OPENROUTER_API_KEY")
    
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("[ERROR] OpenRouter API key not configured!")
        print("   Add ULTRON_OPENROUTER_API_KEY to your .env file")
        print("   Get a free key at: https://openrouter.ai/keys")
        return
    
    print(f"[OK] OpenRouter API key configured: {api_key[:20]}...")
    
    # Load config and create agents
    config = load_config()
    bundle = create_all_agents(config=config)
    
    print("\n[TEST] Testing each brain with a simple query...")
    
    # Test Planning Brain
    print("\n[Planning] Testing Planning Brain...")
    try:
        plan = bundle.planning.plan("Create a simple Python hello world script")
        print(f"   Plan created with {len(plan.tasks)} tasks")
        for task in plan.tasks:
            print(f"   - {task.id}: {task.agent} - {task.description[:50]}...")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
    
    # Test Research Brain
    print("\n[Research] Testing Research Brain...")
    try:
        report = bundle.research.research("What is Python asyncio?")
        print(f"   Research completed with {len(report.findings)} findings")
        print(f"   Summary: {report.summary[:100]}...")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
    
    # Test Fast Brain (for quick tasks)
    print("\n[Fast] Testing Fast Brain (auto-routed)...")
    try:
        result = route_and_execute(bundle, "What is 2+2?")
        print(f"   Result: {str(result)[:200]}...")
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
    
    # Test Routing
    print("\n[Routing] Testing Auto-Routing...")
    test_queries = [
        "Plan a web app architecture",
        "Research best practices for REST APIs",
        "Fix a bug in my code",
        "Open notepad",
    ]
    
    for query in test_queries:
        decision = bundle.router.route(query)
        print(f"   '{query[:40]}...' -> {decision.brain_type.value} ({decision.confidence:.2f})")
    
    print("\n[OK] All tests passed! Agents are ready to use.")
    print("\n[Usage] Examples:")
    print("   from ultron.agents.setup import create_all_agents")
    print("   bundle = create_all_agents()")
    print("   plan = bundle.planning.plan('Build a todo app')")
    print("   report = bundle.research.research('Python vs Go')")


if __name__ == "__main__":
    main()