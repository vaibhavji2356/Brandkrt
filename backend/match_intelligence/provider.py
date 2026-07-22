"""Specialized Responses API boundary; existing discovery providers are untouched."""

from abc import ABC, abstractmethod
import asyncio
import json
from typing import Any

import httpx

from brand_discovery_ai.config import AISettings
from brand_discovery_ai.providers import OPENAI_RESPONSES_URL, RETRYABLE_HTTP_STATUS_CODES

from .models import ProviderPayload
from .prompting import MatchPrompt


class MatchProviderError(RuntimeError):
    pass


class MatchReasoningProvider(ABC):
    @abstractmethod
    async def reason(self, prompt: MatchPrompt) -> Any: ...


class OpenAIMatchReasoningProvider(MatchReasoningProvider):
    def __init__(self, settings: AISettings, http_transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings.validate()
        if not settings.openai_enabled:
            raise MatchProviderError("Match reasoning provider is disabled.")
        self._transport = http_transport

    async def reason(self, prompt: MatchPrompt) -> Any:
        schema = provider_response_schema()
        body = {
            "model": self.settings.model,
            "input": prompt.as_messages(),
            "text": {
                "verbosity": "low",
                "format": {"type": "json_schema", "name": "creator_match_intelligence", "strict": True, "schema": schema},
            },
            "reasoning": {"effort": "none"},
            "max_output_tokens": self.settings.max_output_tokens,
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"}
        attempts = self.settings.max_retries + 1
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=httpx.Timeout(self.settings.timeout_seconds)) as client:
                    response = await client.post(OPENAI_RESPONSES_URL, headers=headers, json=body)
            except (httpx.TimeoutException, httpx.RequestError):
                if attempt + 1 < attempts:
                    continue
                raise MatchProviderError("Match reasoning provider is unavailable.") from None
            if response.status_code in RETRYABLE_HTTP_STATUS_CODES and attempt + 1 < attempts:
                continue
            if response.status_code >= 400:
                raise MatchProviderError("Match reasoning provider rejected the request.")
            return _extract_json(response)
        raise MatchProviderError("Match reasoning provider is unavailable.")


def provider_response_schema() -> dict[str, Any]:
    schema = ProviderPayload.model_json_schema(mode="validation")
    return _strict_schema(schema)


def _strict_schema(value):
    if isinstance(value, dict):
        result = {key: _strict_schema(item) for key, item in value.items()}
        if result.get("type") == "object":
            result["additionalProperties"] = False
            properties = result.get("properties", {})
            result["required"] = list(properties)
        return result
    if isinstance(value, list):
        return [_strict_schema(item) for item in value]
    return value


def _extract_json(response: httpx.Response) -> Any:
    try:
        data = response.json()
    except ValueError:
        raise MatchProviderError("Match reasoning provider returned invalid data.") from None
    direct = data.get("output_text") if isinstance(data, dict) else None
    if isinstance(direct, str):
        try:
            return json.loads(direct)
        except ValueError:
            raise MatchProviderError("Match reasoning provider returned invalid data.") from None
    for output in data.get("output", []) if isinstance(data, dict) else []:
        for content in output.get("content", []) if isinstance(output, dict) else []:
            if content.get("type") == "refusal":
                raise MatchProviderError("Match reasoning provider refused the request.")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                try:
                    return json.loads(content["text"])
                except ValueError:
                    raise MatchProviderError("Match reasoning provider returned invalid data.") from None
    raise MatchProviderError("Match reasoning provider returned no result.")
