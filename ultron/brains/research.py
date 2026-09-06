"""Research Brain for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

The Research Brain is responsible for:
- Understanding research questions
- Formulating searches
- Collecting sources
- Extracting facts
- Comparing sources
- Synthesizing results
- Returning structured findings

The Research Brain uses the existing ToolRegistry for web/search tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.brains.research")

RESEARCH_SYSTEM_PROMPT = """You are the Research Brain for JARVIS. Your role is to gather information, analyze sources, and provide structured findings.

You have access to research tools: read_file, search_files, open_url, get_system_info

Given a research question, you should:
1. Use available tools to gather information
2. Collect sources and evidence
3. Analyze and compare information
4. Provide structured findings with sources

Always cite your sources when providing factual information."""


@dataclass
class ResearchFinding:
    """A single research finding with source."""

    content: str
    source: str = ""
    source_type: str = "unknown"
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "source_type": self.source_type,
            "confidence": self.confidence,
        }


@dataclass
class ResearchReport:
    """Complete research report with findings."""

    question: str
    findings: List[ResearchFinding]
    summary: str = ""
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "sources": self.sources,
        }


class ResearchBrain(BaseAgent):
    """Specialized agent for research and information gathering."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 12,
        tool_executor: Optional[Any] = None,
    ) -> None:
        spec = AgentSpec(
            name="research",
            description="Information gathering, source analysis, evidence collection",
            capabilities=[AgentCapability.RESEARCH],
            allowed_tools=["read_file", "search_files", "open_url", "get_system_info"],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)
        self._tool_executor = tool_executor

    def research(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> ResearchReport:
        """Conduct research and produce a structured report.

        Args:
            user_text: The research question
            context: Optional context

        Returns:
            ResearchReport with findings
        """
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_names = {t.name for t in available_tools}

        findings: List[ResearchFinding] = []

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(
                user_text if iteration == 0 else None,
                tool_specs,
            )

            if not result.tool_calls:
                break

            tool_results = []
            for call in result.tool_calls:
                if call.name in tool_names:
                    try:
                        if self._tool_executor is not None:
                            exec_result = self._tool_executor.execute(call.name, call.arguments)
                            output = exec_result.output
                            if exec_result.error:
                                output = {"error": exec_result.error}
                        else:
                            tool_map = {t.name: t for t in available_tools}
                            output = tool_map[call.name].run(**call.arguments)
                        source_type = self._infer_source_type(call.name, output)
                        finding = ResearchFinding(
                            content=str(output)[:2000],
                            source=call.name,
                            source_type=source_type,
                            confidence=0.8,
                        )
                        findings.append(finding)
                    except Exception as exc:
                        logger.error("ResearchBrain tool %s failed: %s", call.name, exc)
                        finding = ResearchFinding(
                            content=f"Error: {exc}",
                            source=call.name,
                            source_type="error",
                            confidence=0.0,
                        )
                        findings.append(finding)
                        output = str(exc)
                else:
                    output = f"Tool not available: {call.name}"

                output_str = output if isinstance(output, str) else str(output)
                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        summary = self._generate_summary(findings)
        sources = list(set(f.source for f in findings if f.source not in ("error", "unknown")))

        return ResearchReport(
            question=user_text,
            findings=findings,
            summary=summary,
            sources=sources,
        )

    def _infer_source_type(self, tool_name: str, output: Any) -> str:
        if "file" in tool_name:
            return "file"
        if "search" in tool_name or "url" in tool_name or "web" in tool_name:
            return "web"
        if "system" in tool_name:
            return "system"
        return "unknown"

    def _generate_summary(self, findings: List[ResearchFinding]) -> str:
        if not findings:
            return "No findings collected."

        successful = [f for f in findings if f.confidence > 0.3]
        if not successful:
            return "Research completed but no reliable findings."

        return f"Research completed. Found {len(successful)} reliable findings."

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute research task - returns JSON report as string."""
        report = self.research(user_text, context)
        return json.dumps(report.to_dict(), ensure_ascii=False, default=str)


__all__ = ["ResearchBrain", "ResearchFinding", "ResearchReport"]
