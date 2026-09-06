"""Anthropic provider — Claude models.

Uses Anthropic's Messages API:
https://docs.anthropic.com/claude/reference/messages
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if TYPE_CHECKING:
    from ultron.tools.base import ToolSpec


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider.

    Uses Anthropic's Messages API with tool use support.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        base_url: str = "https://api.anthropic.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        self._messages: List[Dict[str, Any]] = []

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        if text is not None:
            self._messages.append({"role": "user", "content": text})

        payload: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": self._messages,
        }

        if self._system_prompt:
            payload["system"] = self._system_prompt

        if self._temperature != 1.0:
            payload["temperature"] = self._temperature

        if tools:
            tool_declarations = []
            for spec in tools:
                tool_declarations.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.parameters,
                    }
                )
            payload["tools"] = tool_declarations

        response = self._client.post(
            "/messages",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        for result in results:
            self._messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": result.call.id,
                            "content": result.output,
                        }
                    ],
                }
            )

    def _parse_response(self, data: Dict[str, Any]) -> ProviderResult:
        content = data.get("content", [])

        text: Optional[str] = None
        tool_calls: List[ToolCall] = []

        for block in content:
            if block.get("type") == "text":
                text = block.get("text")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        if tool_calls:
            self._messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )
        elif text:
            self._messages.append(
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": text}],
                }
            )

        return ProviderResult(text=text, tool_calls=tool_calls)


__all__ = ["AnthropicProvider"]
