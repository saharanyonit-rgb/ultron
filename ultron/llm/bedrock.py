"""AWS Bedrock provider — Claude, Llama, Mistral, etc.

Uses AWS Bedrock's API with SigV4 signing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from ultron.llm.base import LLMProvider, ProviderResult, ToolCall, ToolResult

if TYPE_CHECKING:
    from ultron.tools.base import ToolSpec


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider.

    Supports multiple models: Claude, Llama, Mistral, etc.
    Uses AWS SigV4 signing for authentication.

    Region defaults to us-east-1. Set AWS_BEDROCK_REGION env var to change.
    """

    name = "bedrock"

    def __init__(
        self,
        region: str,
        access_key: str,
        secret_key: str,
        model: str = "anthropic.claude-sonnet-4-20250514",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> None:
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._base_url = f"https://bedrock.{region}.amazonaws.com"
        self._messages: List[Dict[str, Any]] = []

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signing_key(self, secret_key: str, date: str, region: str, service: str) -> bytes:
        k_date = self._sign(("AWS4" + secret_key).encode("utf-8"), date)
        k_region = self._sign(k_date, region)
        k_service = self._sign(k_region, service)
        k_signing = self._sign(k_service, "aws4_request")
        return k_signing

    def _aws_sigv4_headers(
        self,
        method: str,
        url: str,
        body: str,
        service: str = "bedrock",
    ) -> Dict[str, str]:
        t = datetime.utcnow()
        amz_date = t.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = t.strftime("%Y%m%d")

        parsed = urlparse(url)
        canonical_uri = parsed.path or "/"
        canonical_querystr = parsed.query or ""

        payload_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

        headers_to_sign = {
            "content-type": "application/json",
            "x-amz-date": amz_date,
            "host": parsed.netloc,
        }

        canonical_headers = "\n".join(f"{k.lower()}:{v}" for k, v in sorted(headers_to_sign.items())) + "\n"
        signed_headers = ";".join(k.lower() for k in sorted(headers_to_sign.keys()))

        canonical_request = f"{method}\n{canonical_uri}\n{canonical_querystr}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self._region}/{service}/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        signing_key = self._get_signing_key(self._secret_key, date_stamp, self._region, service)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self._access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization_header,
            "content-type": "application/json",
        }

    def _is_anthropic_model(self) -> bool:
        return self._model.startswith("anthropic.")

    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        if text is not None:
            self._messages.append({"role": "user", "content": [{"text": text}] if self._is_anthropic_model() else text})

        if self._is_anthropic_model():
            return self._complete_anthropic(tools)
        else:
            return self._complete_openai(tools)

    def _complete_anthropic(self, tools: List["ToolSpec"]) -> ProviderResult:
        system_content = self._system_prompt or ""

        payload: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": self._messages,
        }

        if system_content:
            payload["system"] = system_content

        if tools:
            tools_dict = []
            for spec in tools:
                tools_dict.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.parameters,
                    }
                )
            payload["tools"] = tools_dict

        body = json.dumps(payload)
        url = f"{self._base_url}/model/{self._model}/invoke"
        headers = self._aws_sigv4_headers("POST", url, body, "bedrock")

        response = httpx.post(
            url,
            content=body,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()

        data = json.loads(response.text)
        return self._parse_anthropic_response(data)

    def _complete_openai(self, tools: List["ToolSpec"]) -> ProviderResult:
        if self._system_prompt and not any(m.get("role") == "system" for m in self._messages):
            self._messages.insert(0, {"role": "system", "content": self._system_prompt})

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

        body = json.dumps(payload)
        url = f"{self._base_url}/model/{self._model}/invoke"
        headers = self._aws_sigv4_headers("POST", url, body, "bedrock")

        response = httpx.post(
            url,
            content=body,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()

        data = json.loads(response.text)
        return self._parse_openai_response(data)

    def _parse_anthropic_response(self, data: Dict[str, Any]) -> ProviderResult:
        content = data.get("completion", {}).get("content", [])

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

        if text:
            self._messages.append({"role": "assistant", "content": [{"text": text}]})

        return ProviderResult(text=text, tool_calls=tool_calls)

    def _parse_openai_response(self, data: Dict[str, Any]) -> ProviderResult:
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

    def feed_tool_results(self, results: List[ToolResult]) -> None:
        for result in results:
            if self._is_anthropic_model():
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
            else:
                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.call.id,
                        "name": result.call.name,
                        "content": result.output,
                    }
                )


__all__ = ["BedrockProvider"]
