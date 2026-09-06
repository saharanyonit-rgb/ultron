"""Cohere provider — Command models.

Uses Cohere's Chat API with tool support.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if TYPE_CHECKING:
    from ultron.tools.base import ToolSpec


class CohereProvider(LLMProvider):
    """Cohere provider.

    Uses Cohere's Chat API:
    https://docs.cohere.com/docs/chat-api
    """

    name = "cohere"

    def __init__(
        self,
        api_key: str,
        model: str = "command-a",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        base_url: str = "https://api.cohere.ai/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Cohere-version": "2024-10-01",
            },
        )
        self._messages: List[Dict[str, Any]] = []

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        if text is not None:
            self._messages.append({"role": "User", "content": text})

        payload: Dict[str, Any] = {
            "model": self._model,
            "chat_history": self._messages,
            "message": text if text else "",
            "temperature": self._temperature,
        }

        if self._system_prompt:
            payload["system_prompt"] = self._system_prompt

        if tools:
            tools_dict = []
            for spec in tools:
                tools_dict.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "parameter_definitions": spec.parameters,
                    }
                )
            payload["tools"] = tools_dict

        response = self._client.post(
            "/chat",
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        for result in results:
            self._messages.append(
                {
                    "role": "Tool",
                    "tool_results": {
                        "call": {"name": result.call.name, "parameters": result.call.arguments},
                        "outputs": [{"text": result.output}],
                    },
                }
            )

    def _parse_response(self, data: Dict[str, Any]) -> ProviderResult:
        text = data.get("text", "")
        tool_calls: List[ToolCall] = []

        if "tool_calls" in data:
            for tc in data.get("tool_calls", []):
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=tc.get("name", ""),
                        arguments=tc.get("input", {}),
                    )
                )

        self._messages.append({"role": "Chatbot", "content": text})

        return ProviderResult(text=text, tool_calls=tool_calls)


__all__ = ["CohereProvider"]
