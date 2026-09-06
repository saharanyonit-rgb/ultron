"""Computer Brain for JARVIS Phase 7 - Multi-Model Specialized Brain Architecture.

The Computer Brain is responsible for:
- Understanding computer-control goals
- Determining required actions
- Using existing browser/keyboard/mouse/application tools
- Inspecting results
- Recovering from expected failures
- Requesting verification

The Computer Brain respects all existing risk classification and permission
requirements. It does NOT have unrestricted OS access.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.brains.computer")

COMPUTER_SYSTEM_PROMPT = """You are the Computer Brain for JARVIS. Your role is to control the computer to accomplish user tasks.

You have access to computer control tools: open_app, close_app, open_url, take_screenshot, get_system_info

Rules:
- Use appropriate tools for the requested action
- Report the result of each action
- If a tool fails, report the error
- Do NOT use unrestricted command execution
- All actions must go through the tool system
- Request verification when an action is complete"""

COMPUTER_TOOLS = [
    "open_app",
    "close_app",
    "open_url",
    "take_screenshot",
    "get_system_info",
    "get_clipboard",
    "set_clipboard",
]


@dataclass
class ComputerAction:
    """A computer control action."""

    action_type: str
    target: str
    result: str = ""
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "result": self.result,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ComputerResult:
    """Result of a computer control task."""

    task: str
    actions: List[ComputerAction]
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
        }


class ComputerBrain(BaseAgent):
    """Specialized agent for computer control tasks."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 8,
        tool_executor: Optional[Any] = None,
    ) -> None:
        spec = AgentSpec(
            name="computer",
            description="Computer control, browser automation, application management",
            capabilities=[AgentCapability.GENERAL],
            allowed_tools=COMPUTER_TOOLS,
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)
        self._tool_executor = tool_executor

    def execute(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> ComputerResult:
        """Execute a computer control task.

        Args:
            user_text: The computer control task description
            context: Optional context

        Returns:
            ComputerResult with actions and results
        """
        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_names = {t.name for t in available_tools}

        actions: List[ComputerAction] = []

        for iteration in range(self._spec.max_iterations):
            result = self._provider.complete(
                user_text if iteration == 0 else None,
                tool_specs,
            )

            if not result.tool_calls:
                if result.text:
                    actions.append(ComputerAction(
                        action_type="response",
                        target="",
                        result=result.text,
                        success=True,
                    ))
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
                        action_type = self._infer_action_type(call.name)
                        target = self._get_target(call.name, call.arguments)
                        action = ComputerAction(
                            action_type=action_type,
                            target=target,
                            result=str(output)[:500],
                            success=True,
                        )
                        actions.append(action)
                    except Exception as exc:
                        logger.error("ComputerBrain tool %s failed: %s", call.name, exc)
                        target = self._get_target(call.name, call.arguments)
                        action = ComputerAction(
                            action_type=self._infer_action_type(call.name),
                            target=target,
                            result="",
                            success=False,
                            error=str(exc),
                        )
                        actions.append(action)
                        output = str(exc)
                    output_str = output if isinstance(output, str) else str(output)
                else:
                    output_str = f"Tool not available: {call.name}"

                tool_results.append(ToolResult(call=call, output=output_str))

            self._provider.feed_tool_results(tool_results)

        summary = self._generate_summary(actions)

        return ComputerResult(
            task=user_text,
            actions=actions,
            summary=summary,
        )

    def _infer_action_type(self, tool_name: str) -> str:
        if "open" in tool_name:
            return "open"
        if "close" in tool_name:
            return "close"
        if "screenshot" in tool_name:
            return "screenshot"
        if "url" in tool_name or "browse" in tool_name:
            return "navigate"
        if "clipboard" in tool_name:
            return "clipboard"
        if "system" in tool_name or "info" in tool_name:
            return "info"
        return "unknown"

    def _get_target(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if "path" in arguments:
            return arguments["path"]
        if "url" in arguments:
            return arguments["url"]
        if "app" in arguments:
            return arguments["app"]
        return tool_name

    def _generate_summary(self, actions: List[ComputerAction]) -> str:
        successful = [a for a in actions if a.success]
        failed = [a for a in actions if not a.success]

        parts = []
        if successful:
            parts.append(f"{len(successful)} actions succeeded")
        if failed:
            parts.append(f"{len(failed)} actions failed")

        return "; ".join(parts) if parts else "No actions performed"

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute computer control task - returns JSON result as string."""
        result = self.execute(user_text, context)
        return json.dumps(result.to_dict(), ensure_ascii=False, default=str)


__all__ = ["ComputerBrain", "ComputerAction", "ComputerResult"]
