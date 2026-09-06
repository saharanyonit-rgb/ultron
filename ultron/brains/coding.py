"""Coding Brain for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

The Coding Brain is responsible for:
- Inspecting repositories
- Understanding existing code
- Identifying bugs
- Creating implementation plans
- Modifying code through approved tools
- Running tests
- Inspecting failures
- Fixing problems
- Reporting evidence

The Coding Brain uses the existing ToolRegistry and must NOT
use unrestricted subprocess/system calls outside the tool architecture.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.brains.coding")

CODING_SYSTEM_PROMPT = """You are the Coding Brain for JARVIS. Your role is to analyze code, implement features, and fix bugs.

You have access to coding tools: read_file, create_file, search_files

Rules:
- Always read existing code before modifying
- Use search to find relevant code
- Create backups or read original before overwriting
- Report what you found and what you changed
- Do NOT use unrestricted command execution
- All changes must go through the tool system"""

CODING_TOOLS = ["read_file", "create_file", "search_files"]


@dataclass
class CodeChange:
    """A code modification."""

    file_path: str
    change_type: str
    description: str
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "description": self.description,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class CodingResult:
    """Result of a coding task."""

    task: str
    changes: List[CodeChange]
    findings: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "changes": [c.to_dict() for c in self.changes],
            "findings": self.findings,
            "summary": self.summary,
        }


class CodingBrain(BaseAgent):
    """Specialized agent for coding tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 10,
        tool_executor: Optional[Any] = None,
    ) -> None:
        spec = AgentSpec(
            name="coding",
            description="Code analysis, implementation planning, test generation",
            capabilities=[AgentCapability.CODING],
            allowed_tools=CODING_TOOLS,
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)
        self._tool_executor = tool_executor

    def execute(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> CodingResult:
        """Execute a coding task.

        Args:
            user_text: The coding task description
            context: Optional context

        Returns:
            CodingResult with changes and findings
        """
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_names = {t.name for t in available_tools}

        changes: List[CodeChange] = []
        findings: List[str] = []

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(
                user_text if iteration == 0 else None,
                tool_specs,
            )

            if not result.tool_calls:
                if result.text:
                    findings.append(result.text)
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
                        findings.append(f"[{call.name}] {output}")

                        if call.name == "create_file":
                            path = call.arguments.get("path", "unknown")
                            change = CodeChange(
                                file_path=path,
                                change_type="create",
                                description=f"Created file: {path}",
                                success=True,
                            )
                            changes.append(change)
                        elif call.name == "read_file":
                            path = call.arguments.get("path", "unknown")
                            change = CodeChange(
                                file_path=path,
                                change_type="read",
                                description=f"Read file: {path}",
                                success=True,
                            )
                            changes.append(change)

                    except Exception as exc:
                        logger.error("CodingBrain tool %s failed: %s", call.name, exc)
                        findings.append(f"[{call.name}] Error: {exc}")
                        path = call.arguments.get("path", "unknown")
                        change = CodeChange(
                            file_path=path,
                            change_type="error",
                            description=f"Error on {call.name}",
                            success=False,
                            error=str(exc),
                        )
                        changes.append(change)
                        output = str(exc)
                    output_str = output if isinstance(output, str) else str(output)
                else:
                    output_str = f"Tool not available: {call.name}"
                    findings.append(output_str)

                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        summary = self._generate_summary(changes, findings)

        return CodingResult(
            task=user_text,
            changes=changes,
            findings=findings,
            summary=summary,
        )

    def _generate_summary(self, changes: List[CodeChange], findings: List[str]) -> str:
        successful = [c for c in changes if c.success]
        failed = [c for c in changes if not c.success]

        parts = []
        if successful:
            parts.append(f"{len(successful)} successful operations")
        if failed:
            parts.append(f"{len(failed)} failed operations")
        if findings:
            parts.append(f"{len(findings)} findings")

        return "; ".join(parts) if parts else "No changes made"

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute coding task - returns JSON result as string."""
        result = self.execute(user_text, context)
        return json.dumps(result.to_dict(), ensure_ascii=False, default=str)


__all__ = ["CodingBrain", "CodeChange", "CodingResult"]
