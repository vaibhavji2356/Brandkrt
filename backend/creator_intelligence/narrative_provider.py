"""One-call structured OpenAI boundary for Creator Intelligence narrative text."""

from abc import ABC, abstractmethod
import json
from typing import Any

import httpx

from brand_discovery_ai.config import AISettings
from brand_discovery_ai.providers import OPENAI_RESPONSES_URL

from .models import PortfolioNarrative
from .narrative_prompting import NarrativePrompt


class NarrativeProviderError(RuntimeError):
    pass


class CreatorNarrativeProvider(ABC):
    @abstractmethod
    async def narrate(self, prompt: NarrativePrompt) -> Any: ...


class OpenAICreatorNarrativeProvider(CreatorNarrativeProvider):
    def __init__(self, settings: AISettings, http_transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings.validate()
        if not settings.openai_enabled:
            raise NarrativeProviderError("Creator narrative provider is disabled.")
        self._transport = http_transport

    async def narrate(self, prompt: NarrativePrompt) -> Any:
        body = {
            "model": self.settings.model,
            "input": prompt.as_messages(),
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema", "name": "creator_intelligence_narrative",
                    "strict": True, "schema": provider_narrative_schema(),
                },
            },
            "reasoning": {"effort": "none"},
            "max_output_tokens": self.settings.max_output_tokens,
            "store": False,
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=httpx.Timeout(self.settings.timeout_seconds)) as client:
                # One narrative request means one provider call; no internal retry loop.
                response = await client.post(OPENAI_RESPONSES_URL, headers=headers, json=body)
        except (httpx.TimeoutException, httpx.RequestError):
            raise NarrativeProviderError("Creator narrative provider is unavailable.") from None
        if response.status_code >= 400:
            raise NarrativeProviderError("Creator narrative provider rejected the request.")
        return _extract_json(response)


def provider_narrative_schema() -> dict[str, Any]:
    return _strict_schema(PortfolioNarrative.model_json_schema(mode="validation"))


def _strict_schema(value: Any) -> Any:
    if isinstance(value, dict):
        result = {key: _strict_schema(item) for key, item in value.items()}
        if result.get("type") == "object":
            result["additionalProperties"] = False
            result["required"] = list(result.get("properties", {}))
        return result
    if isinstance(value, list):
        return [_strict_schema(item) for item in value]
    return value


def _extract_json(response: httpx.Response) -> Any:
    try:
        data = response.json()
    except ValueError:
        raise NarrativeProviderError("Creator narrative provider returned invalid data.") from None
    direct = data.get("output_text") if isinstance(data, dict) else None
    if isinstance(direct, str):
        try:
            return json.loads(direct)
        except ValueError:
            raise NarrativeProviderError("Creator narrative provider returned invalid data.") from None
    for output in data.get("output", []) if isinstance(data, dict) else []:
        for content in output.get("content", []) if isinstance(output, dict) else []:
            if content.get("type") == "refusal":
                raise NarrativeProviderError("Creator narrative provider refused the request.")
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                try:
                    return json.loads(content["text"])
                except ValueError:
                    raise NarrativeProviderError("Creator narrative provider returned invalid data.") from None
    raise NarrativeProviderError("Creator narrative provider returned no result.")
