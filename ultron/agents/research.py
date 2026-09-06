"""Research agent — information gathering, source analysis, evidence collection."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.agents.research")

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool


class ResearchAgent(BaseAgent):
    """Specialized agent for research and information gathering tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 12,
    ) -> None:
        spec = AgentSpec(
            name="research",
            description="Information gathering, source analysis, evidence collection",
            capabilities=[AgentCapability.RESEARCH],
            allowed_tools=["read_file", "search_files", "open_url", "get_system_info"],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute research task: gather information, analyze sources, compile findings."""
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_map = {t.name: t for t in available_tools}

        collected_findings: List[str] = []

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(user_text if iteration == 0 else None, tool_specs)

            if not result.tool_calls:
                return result.text or ""

            tool_results = []
            for call in result.tool_calls:
                if call.name in tool_map:
                    try:
                        output = tool_map[call.name].run(**call.arguments)
                        finding = f"[{call.name}] {output}"
                        collected_findings.append(finding)
                    except Exception as exc:
                        logger.error("ResearchAgent tool %s failed: %s", call.name, exc)
                        finding = f"[{call.name}] Error: {exc}"
                        collected_findings.append(finding)
                    output_str = output if isinstance(output, str) else str(output)
                else:
                    output_str = f"Tool not available: {call.name}"
                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        return f"Research completed. Found {len(collected_findings)} pieces of information."


__all__ = ["ResearchAgent"]
