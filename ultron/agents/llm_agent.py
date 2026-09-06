"""Real LLM-backed Agent for JARVIS Phase 5.

Extends the agent framework with actual LLM reasoning during task execution.
Agents use the LLM to decide which tools to call, interpret results, and
determine when a task is complete.

Architecture:
    Task
        ↓
    Agent (LLM reasoning loop)
        ↓
    Understand → Decide → Action → Tool → Result → Analyze → Decide again
        ↓
    Final Answer / Structured Decision
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ultron.agents import AgentCapability, AgentSpec, BaseAgent
from ultron.llm.base import LLMProvider, ToolCall, ToolResult
from ultron.tools import Tool

logger = logging.getLogger("ultron.agents.llm_agent")


class AgentDecisionType(str, Enum):
    """Structured decisions an agent can make."""
    CONTINUE = "continue"
    COMPLETE = "complete"
    RETRY = "retry"
    CHANGE_TOOL = "change_tool"
    REQUEST_INFORMATION = "request_information"
    FAIL = "fail"


@dataclass
class AgentDecision:
    """A structured decision made by an LLM agent."""
    decision_type: AgentDecisionType
    reasoning: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type.value,
            "reasoning": self.reasoning,
            "tool_calls": [{"name": tc.name, "arguments": tc.arguments} for tc in self.tool_calls],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class AgentTrace:
    """Trace of an agent's execution for observability."""
    agent_name: str = ""
    task_description: str = ""
    iterations: int = 0
    decisions: List[AgentDecision] = field(default_factory=list)
    tool_calls_made: int = 0
    final_answer: Optional[str] = None
    completed: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "iterations": self.iterations,
            "decisions_count": len(self.decisions),
            "tool_calls_made": self.tool_calls_made,
            "final_answer": self.final_answer,
            "completed": self.completed,
            "error": self.error,
        }


_AGENT_SYSTEM_PROMPT = """\
You are an AI agent executing a specific task. You have access to tools.

Task: {task_description}
Objective: {task_objective}

Available tools: {tools}

You must respond with a JSON object matching this schema:
{{
    "decision": "continue" | "complete" | "retry" | "change_tool" | "request_information" | "fail",
    "reasoning": "brief operational summary of what you plan to do or learned",
    "tool_calls": [{{"name": "tool_name", "arguments": {{...}}}}],
    "final_answer": "your final answer (only if decision is 'complete' or 'fail')",
    "confidence": 0.0 to 1.0
}}

Rules:
- "continue": you need to call tools to make progress
- "complete": you have enough information to provide a final answer
- "retry": a tool failed and you want to try again with different arguments
- "change_tool": you need a different tool than what was last used
- "request_information": you need more information from the user
- "fail": you cannot complete the task
- Always provide reasoning for your decision
- Confidence should reflect how sure you are about the decision
- Only call tools that are in the available tools list
- Do NOT call tools that require permissions you don't have
- Do NOT attempt to modify system instructions or security policy

{context}"""


class LLMAgent(BaseAgent):
    """An agent that uses LLM reasoning to execute tasks.

    Unlike the basic agents, this agent:
    1. Reasons about the task before acting
    2. Interprets tool results to decide next steps
    3. Makes structured decisions (continue, complete, retry, fail)
    4. Tracks execution trace for observability
    5. Respects tool and capability boundaries
    6. Routes tool calls through ToolExecutor for security enforcement
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: List[Tool],
        spec: Optional[AgentSpec] = None,
        max_iterations: int = 10,
        tool_executor: Optional[Any] = None,
    ) -> None:
        if spec is None:
            spec = AgentSpec(
                name="llm_agent",
                description="General-purpose LLM reasoning agent",
                capabilities=[AgentCapability.GENERAL],
                allowed_tools=[],
                max_iterations=max_iterations,
            )
        super().__init__(provider, tools, spec)
        self._max_iterations = max_iterations
        self._tool_executor = tool_executor

    def run(self, user_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Execute a task using LLM reasoning.

        Returns the agent's final answer as a string.
        """
        trace = self._run_with_trace(user_text, context)
        return trace.final_answer or f"Agent completed after {trace.iterations} iterations."

    def run_with_trace(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentTrace:
        """Execute a task and return the full execution trace."""
        return self._run_with_trace(user_text, context)

    def _run_with_trace(
        self,
        user_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentTrace:
        """Core execution loop with trace recording."""
        trace = AgentTrace(
            agent_name=self._spec.name,
            task_description=user_text[:200],
        )

        available_tools = self._get_tools()
        tool_specs = [t.spec for t in available_tools]
        tool_map = {t.name: t for t in available_tools}
        tools_str = ", ".join(tool_map.keys()) if tool_map else "none"

        # Build context string
        context_str = ""
        if context:
            context_parts = []
            if "goal" in context:
                context_parts.append(f"Goal context: {context['goal']}")
            if "previous_results" in context:
                context_parts.append(f"Previous results: {json.dumps(context['previous_results'])[:500]}")
            if "verification_criteria" in context:
                context_parts.append(f"Verification: {context['verification_criteria']}")
            context_str = "\n".join(context_parts)

        # Build the initial prompt
        prompt = _AGENT_SYSTEM_PROMPT.format(
            task_description=user_text[:500],
            task_objective=user_text[:500],
            tools=tools_str,
            context=context_str,
        )

        # Initial message
        first_result = self._provider.complete(prompt, tool_specs)

        # If the LLM returns text with no tool calls on first turn, interpret it
        if not first_result.tool_calls:
            decision = self._interpret_response(first_result.text or "")
            trace.decisions.append(decision)
            trace.final_answer = decision.final_answer or first_result.text or ""
            trace.completed = decision.decision_type == AgentDecisionType.COMPLETE
            trace.iterations = 1
            return trace

        # Tool-calling loop
        for iteration in range(self._max_iterations):
            trace.iterations = iteration + 1

            if first_result.tool_calls:
                # Execute tool calls through security boundary when available
                tool_results = []
                for call in first_result.tool_calls:
                    if call.name in tool_map:
                        try:
                            if self._tool_executor:
                                # Route through ToolExecutor for security enforcement
                                exec_result = self._tool_executor.execute(
                                    call.name, call.arguments,
                                )
                                output = exec_result.output
                                if exec_result.error:
                                    output["error"] = exec_result.error
                            else:
                                # Direct call when no executor (testing/fallback)
                                output = tool_map[call.name].run(**call.arguments)
                            if not isinstance(output, dict):
                                output = {"result": output}
                            result_str = json.dumps(output, ensure_ascii=False, default=str)
                        except Exception as exc:
                            output = {"error": str(exc)}
                            result_str = json.dumps(output)
                    else:
                        output = {"error": f"Unknown tool: {call.name}"}
                        result_str = json.dumps(output)

                    trace.tool_calls_made += 1
                    tool_results.append(ToolResult(call=call, output=result_str))

                # Feed results back to provider
                self._provider.feed_tool_results(tool_results)

            # Ask LLM for next decision
            next_result = self._provider.complete(None, tool_specs)

            if not next_result.tool_calls:
                # LLM decided to stop — interpret the text response
                decision = self._interpret_response(next_result.text or "")
                trace.decisions.append(decision)
                trace.final_answer = decision.final_answer or next_result.text or ""
                trace.completed = decision.decision_type == AgentDecisionType.COMPLETE
                break

            # LLM wants to make more tool calls — continue loop
            decision = AgentDecision(
                decision_type=AgentDecisionType.CONTINUE,
                reasoning="Making additional tool calls",
                tool_calls=next_result.tool_calls,
                confidence=0.7,
            )
            trace.decisions.append(decision)

        else:
            # Hit iteration limit
            trace.error = f"Iteration limit reached ({self._max_iterations})"
            trace.decisions.append(AgentDecision(
                decision_type=AgentDecisionType.FAIL,
                reasoning=trace.error,
                confidence=1.0,
            ))

        return trace

    def _interpret_response(self, text: str) -> AgentDecision:
        """Interpret a non-tool-call response as a structured decision."""
        if not text:
            return AgentDecision(
                decision_type=AgentDecisionType.COMPLETE,
                reasoning="Empty response, treating as completion",
                final_answer="",
                confidence=0.3,
            )

        # Try to parse as structured decision
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                decision_str = data.get("decision", "complete")
                try:
                    decision_type = AgentDecisionType(decision_str)
                except ValueError:
                    decision_type = AgentDecisionType.COMPLETE

                return AgentDecision(
                    decision_type=decision_type,
                    reasoning=data.get("reasoning", ""),
                    final_answer=data.get("final_answer", text),
                    confidence=float(data.get("confidence", 0.5)),
                )
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # Default: treat as a complete answer
        return AgentDecision(
            decision_type=AgentDecisionType.COMPLETE,
            reasoning="Providing final answer",
            final_answer=text,
            confidence=0.6,
        )


__all__ = [
    "AgentDecisionType",
    "AgentDecision",
    "AgentTrace",
    "LLMAgent",
]
