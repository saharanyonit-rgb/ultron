"""OpenAI provider — official OpenAI API.

Uses the standard OpenAI Chat Completions API format.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if TYPE_CHECKING:
    from ultron.tools.base import ToolSpec


class OpenAIProvider(LLMProvider):
    """OpenAI official API provider.

    Uses OpenAI's Chat Completions API:
    https://platform.openai.com/docs/api-reference/chat
    """

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        system_prompt: str | None = None,
        temperature: float = 0.3,
        base_url: str = "https://api.openai.com/v1",
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
            },
        )
        self._messages: list[dict[str, Any]] = []

    def complete(self, text: str | None, tools: list[ToolSpec]) -> ProviderResult:
        if self._system_prompt and not self._messages:
            self._messages.append({"role": "system", "content": self._system_prompt})

        if text is not None:
            self._messages.append({"role": "user", "content": text})

        payload: dict[str, Any] = {
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

        response = self._post_with_retry(payload)
        response.raise_for_status()
        return self._parse_response(response.json())

    def _post_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        """POST with bounded backoff on rate limits and transient upstream errors.

        Groq's free tier caps tokens-per-minute, so a tool-heavy agent turn can
        legitimately exceed the budget and get a 429. Without a retry that
        surfaced to the user as a raw `HTTPStatusError`. Retries only statuses
        that are safe to repeat (no side effects are performed server-side on a
        rejected request).
        """
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post(
                    "/chat/completions",
                    json=payload,
                    timeout=self._timeout,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt == self._max_retries:
                    raise
                delay = self._backoff_delay(attempt, None)
                logger.warning(
                    "LLM transport error (attempt %d/%d): %s; retrying in %.1fs",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    delay,
                )
                time.sleep(delay)
                continue

            if response.status_code not in _RETRY_STATUSES:
                return response
            if attempt == self._max_retries:
                return response

            delay = self._backoff_delay(attempt, response)
            logger.warning(
                "LLM %d from %s (attempt %d/%d); retrying in %.1fs",
                response.status_code,
                self._base_url,
                attempt + 1,
                self._max_retries + 1,
                delay,
            )
            time.sleep(delay)

        # Unreachable: the loop either returns a response or re-raises.
        raise last_error or RuntimeError("LLM request failed with no response")

    def _backoff_delay(self, attempt: int, response: httpx.Response | None) -> float:
        """Prefer the server's `Retry-After`, else exponential backoff."""
        if response is not None:
            retry_after = response.headers.get("retry-after")
            if retry_after:
                try:
                    return min(float(retry_after), self._max_backoff)
                except ValueError:
                    pass
        return min(self._base_backoff * (2**attempt), self._max_backoff)

    def feed_tool_results(self, results: list[ToolResult]) -> None:
        for result in results:
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result.call.id,
                    "name": result.call.name,
                    "content": result.output,
                }
            )

    def _parse_response(self, data: dict[str, Any]) -> ProviderResult:
        choices = data.get("choices", [])
        if not choices:
            return ProviderResult(text=None, tool_calls=[])

        choice = choices[0]
        message = choice.get("message", {})

        text: str | None = message.get("content")
        raw_tools = message.get("tool_calls", [])

        assistant_turn: dict[str, Any] = {"role": "assistant", "content": text}
        if raw_tools:
            assistant_turn["tool_calls"] = raw_tools
        self._messages.append(assistant_turn)

        tool_calls: list[ToolCall] = []
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


__all__ = ["OpenAIProvider"]
