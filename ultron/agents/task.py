"""Task agent — general multi-step execution, plan following."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.agents.task")


class TaskAgent(BaseAgent):
    """Specialized agent for multi-step task execution."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 8,
    ) -> None:
        spec = AgentSpec(
            name="task",
            description="General multi-step execution, plan following",
            capabilities=[AgentCapability.TASK, AgentCapability.GENERAL],
            allowed_tools=[],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute multi-step task following a plan or ad-hoc instructions."""
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_map = {t.name: t for t in available_tools}

        steps_completed = 0

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(user_text if iteration == 0 else None, tool_specs)

            if not result.tool_calls:
                return result.text or ""

            tool_results = []
            for call in result.tool_calls:
                if call.name in tool_map:
                    try:
                        output = tool_map[call.name].run(**call.arguments)
                        steps_completed += 1
                    except Exception as exc:
                        logger.error("TaskAgent tool %s failed: %s", call.name, exc)
                        output = {"error": str(exc)}
                    output_str = output if isinstance(output, str) else str(output)
                else:
                    output_str = f"Tool not available: {call.name}"
                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        return f"Task completed. Executed {steps_completed} steps."


__all__ = ["TaskAgent"]
