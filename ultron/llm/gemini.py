"""Google Gemini provider — the single V1 model implementation.

Uses the official `google-genai` SDK with manual function-calling control
(we execute tools ourselves so the agent loop owns audit logging and the
permission gate). Tool schemas are passed straight through as JSON Schema.
"""

from __future__ import annotations

from google.api_core.exceptions import GoogleAPIError

import base64
import json
import uuid
import logging
import re
from typing import TYPE_CHECKING, Any, List, Optional

from google import genai
from google.genai import types as gt

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult
from ultron.errors import QuotaError, ProviderError, RateLimitError

if TYPE_CHECKING:  # type-only import — avoids any circular import with tools
    from ultron.tools.base import ToolSpec


logger = logging.getLogger("ultron.llm.gemini")


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> None:
        self._gt = gt
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        # Native conversation buffer — the provider owns its own format.
        self._contents: list[Any] = []

    # -- LLMProvider ---------------------------------------------------

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        if text is not None:
            self._contents.append(
                self._gt.Content(role="user", parts=[self._gt.Part.from_text(text=text)])
            )
        config = self._gt.GenerateContentConfig(
            system_instruction=self._system_prompt,
            temperature=self._temperature,
            tools=[self._to_tool(spec) for spec in tools] if tools else None,
        )
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=self._contents,
                config=config,
            )
        except GoogleAPIError as exc:
            self._handle_google_api_error(exc)
        return self._parse_response(response)

    def _handle_google_api_error(self, exc: Exception) -> None:
        """Classify and raise appropriate error from Google API exceptions."""
        # Extract status code if available
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        error_message = str(exc).lower()

        # Check for quota exhaustion (429 RESOURCE_EXHAUSTED)
        if status_code == 429 or "quota" in error_message or "resource_exhausted" in error_message:
            raise QuotaError(
                provider="gemini",
                model=self._model,
                message=str(exc),
                retryable=False,
            ) from exc

        # Check for rate limit (429 with retry info)
        if status_code == 429 or "rate limit" in error_message:
            raise RateLimitError(
                provider="gemini",
                model=self._model,
                message=str(exc),
                retryable=True,
            ) from exc

        # Check for authentication error
        if "auth" in error_message or "invalid api key" in error_message or "api key" in error_message:
            raise AuthenticationError(
                provider="gemini",
                model=self._model,
                message=str(exc),
            ) from exc

        # Generic provider error
        raise ProviderError(
            provider="gemini",
            model=self._model,
            message=str(exc),
        ) from exc

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        parts = []
        for result in results:
            payload: dict[str, Any] = {"result": result.output}
            try:
                parsed = json.loads(result.output)
                payload = {"result": parsed}
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                part = self._gt.Part.from_function_response(
                    name=result.call.name,
                    response=payload,
                    id=result.call.id,
                )
            except TypeError:
                part = self._gt.Part.from_function_response(
                    name=result.call.name, response=payload
                )
            parts.append(part)
        self._contents.append(self._gt.Content(role="tool", parts=parts))

    # -- internals -----------------------------------------------------

    def _to_tool(self, spec: "ToolSpec") -> Any:
        gt = self._gt
        return gt.Tool(
            function_declarations=[
                gt.FunctionDeclaration(
                    name=spec.name,
                    description=spec.description,
                    parameters_json_schema=spec.parameters,
                )
            ]
        )

    def _parse_response(self, response: Any) -> ProviderResult:
        gt = self._gt
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for candidate in response.candidates or []:
            for part in candidate.content.parts:
                function_call = getattr(part, "function_call", None)
                if function_call is not None:
                    call_id = getattr(function_call, "id", None) or str(uuid.uuid4())
                    tool_calls.append(
                        ToolCall(
                            id=call_id,
                            name=function_call.name,
                            arguments=dict(function_call.args or {}),
                        )
                    )
                if part.text:
                    text_parts.append(part.text)
        text = "".join(text_parts) if text_parts else None
        return ProviderResult(text=text, tool_calls=tool_calls)


    def supports_vision(self) -> bool:
        return True

    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Analyze an image using Gemini's vision capability."""
        gt = self._gt
        from google.genai.types import Image as GenImage

        img_path = Path(image_path)
        if not img_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image_bytes = img_path.read_bytes()
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        img_obj = GenImage(inline_bytes=encoded)

        user_content = gt.Content(
            role="user",
            parts=[
                gt.Part.from_image(image=img_obj),
                gt.Part.from_text(text=prompt),
            ]
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[user_content],
        )

        if not response.text:
            return "(no analysis returned)"
        return response.text
