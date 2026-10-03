"""Coding agent — code analysis, implementation planning, test generation."""

from __future__ import annotations

import logging
from typing import Any

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.agents.coding")


class CodingAgent(BaseAgent):
    """Specialized agent for code analysis and generation tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[Tool],
        max_iterations: int = 10,
    ) -> None:
        spec = AgentSpec(
            name="coding",
            description="Code analysis, implementation planning, test generation",
            capabilities=[AgentCapability.CODING],
            allowed_tools=["read_file", "create_file", "search_files"],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)

    def run(self, user_text: str, context: dict[str, Any] | None = None) -> str:
        """Execute coding task: analyze code, plan implementation, generate tests."""
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_map = {t.name: t for t in available_tools}

        code_artifacts: list[dict[str, Any]] = []

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(user_text if iteration == 0 else None, tool_specs)

            if not result.tool_calls:
                return result.text or ""

            tool_results = []
            for call in result.tool_calls:
                if call.name in tool_map:
                    try:
                        output = tool_map[call.name].run(**call.arguments)
                        code_artifacts.append(
                            {
                                "tool": call.name,
                                "arguments": call.arguments,
                                "output": output,
                            }
                        )
                    except Exception as exc:
                        logger.error("CodingAgent tool %s failed: %s", call.name, exc)
                        code_artifacts.append(
                            {
                                "tool": call.name,
                                "error": str(exc),
                            }
                        )
                    output_str = output if isinstance(output, str) else str(output)
                else:
                    output_str = f"Tool not available: {call.name}"
                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        return f"Coding task completed. Processed {len(code_artifacts)} code operations."


__all__ = ["CodingAgent"]
