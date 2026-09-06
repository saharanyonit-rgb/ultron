"""Vision agent — screen capture and visual analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider
from ultron.tools import Tool


class VisionAgent(BaseAgent):
    """Specialized agent for visual screen analysis and understanding."""

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        max_iterations: int = 5,
    ) -> None:
        spec = AgentSpec(
            name="vision",
            description="Screen capture and visual analysis of the current desktop view",
            capabilities=[AgentCapability.VISION],
            allowed_tools=["vision_analyze"],
            max_iterations=max_iterations,
        )
        super().__init__(provider, tools, spec)

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Analyze the screen and provide visual understanding."""
        available_tools = self._get_tools()
        tool_map = {t.name: t for t in available_tools}
        tool_specs = [t.spec for t in available_tools]

        vision_tool = tool_map.get("vision_analyze")
        if not vision_tool:
            return "Vision tool not available. Screen capture is required for visual analysis."

        prompt = user_text if user_text else "Describe what is currently displayed on the screen."
        result = vision_tool.run(prompt=prompt)
        return result.get("analysis", result.get("error", "No analysis returned."))


__all__ = ["VisionAgent"]
