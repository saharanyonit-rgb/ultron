"""Grok provider — xAI's OpenAI-compatible API.

xAI's Grok models are accessible via an OpenAI-compatible API.
https://console.x.ai/
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if TYPE_CHECKING:
    from ultron.tools.base import ToolSpec


class GrokProvider(LLMProvider):
    """Grok provider implementation via xAI.

    Uses xAI's OpenAI-compatible endpoint:
    https://api.x.ai/v1
    """

    name = "grok"

    def __init__(
        self,
        api_key: str,
        model: str = "latest",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._base_url = "https://api.x.ai/v1"
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._messages: List[Dict[str, Any]] = []

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        if self._system_prompt and not self._messages:
            self._messages.append({"role": "system", "content": self._system_prompt})

        if text is not None:
            self._messages.append({"role": "user", "content": text})

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": self._messages,
            "temperature": self._temperature,
        }

        if tools:
            tool_declarations = []
            for spec in tools:
                tool_declarations.append(
                    {
                        "type": "function",
                        "function": {
                            "name": spec.name,
                            "description": spec.description,
                            "parameters": spec.parameters,
                        },
                    }
                )
            payload["tools"] = tool_declarations
            payload["tool_choice"] = "auto"

        response = self._client.post(
            "/chat/completions",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        for result in results:
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result.call.id,
                    "name": result.call.name,
                    "content": result.output,
                }
            )

    def _parse_response(self, data: Dict[str, Any]) -> ProviderResult:
        choices = data.get("choices", [])
        if not choices:
            return ProviderResult(text=None, tool_calls=[])

        choice = choices[0]
        message = choice.get("message", {})

        text: Optional[str] = message.get("content")
        raw_tools = message.get("tool_calls", [])

        assistant_turn: Dict[str, Any] = {"role": "assistant", "content": text}
        if raw_tools:
            assistant_turn["tool_calls"] = raw_tools
        self._messages.append(assistant_turn)

        tool_calls: List[ToolCall] = []
        for tc in raw_tools:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}

            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=args,
                )
            )

        return ProviderResult(text=text, tool_calls=tool_calls)


__all__ = ["GrokProvider"]
