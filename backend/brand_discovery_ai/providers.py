"""Vendor-neutral provider interface, deterministic mock, and OpenAI adapter."""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Optional

import httpx

from .config import AISettings
from .errors import (
    AIConfigurationError,
    AIProviderOutputError,
    AIProviderUnavailableError,
    RetryableProviderError,
)
from .prompting import BrandDiscoveryPrompt
from .schemas import BrandDiscoveryRequest


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
RETRYABLE_HTTP_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ProviderGeneration:
    raw_output: Any
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class BrandDiscoveryProvider(ABC):
    name: str
    is_mock: bool = False

    @abstractmethod
    async def generate(self, *, prompt: BrandDiscoveryPrompt, request: BrandDiscoveryRequest) -> Any:
        raise NotImplementedError


class MockBrandDiscoveryProvider(BrandDiscoveryProvider):
    name = "mock"
    is_mock = True

    _PREFIXES = (
        "Northstar", "Mosaic", "Evergreen", "Bluebird", "Summit",
        "Harbor", "Wildflower", "Cedar", "Orbit", "Kindred",
        "Sunrise", "Vertex", "Juniper", "Lighthouse", "Meridian",
        "Canopy", "Ember", "Atlas", "Nova", "Terrace",
    )

    async def generate(self, *, prompt: BrandDiscoveryPrompt, request: BrandDiscoveryRequest) -> dict:
        del prompt
        criteria = request.model_dump(mode="json", exclude_none=True)
        seed = int(hashlib.sha256(json.dumps(criteria, sort_keys=True).encode("utf-8")).hexdigest()[:8], 16)
        industry = request.industry or request.niche or "Lifestyle"
        niche = request.niche or industry
        location = request.location or "India"
        platform = (request.preferred_platforms or ["Instagram"])[0]
        audience = request.target_audience or "digitally active consumers"
        objective = request.campaign_objective or "creator-led brand awareness"
        results = []

        for index in range(request.result_limit):
            prefix = self._PREFIXES[(seed + index) % len(self._PREFIXES)]
            brand_name = _truncate(f"{prefix} {industry.title()}", 120)
            slug = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-") or f"brand-{index + 1}"
            relevance = max(55.0, min(98.0, 94.0 - (index * 1.7) + ((seed % 5) * 0.4)))
            confidence = max(50.0, min(96.0, 88.0 - (index * 1.2) + ((seed % 3) * 0.5)))
            results.append({
                "brand_name": brand_name,
                "website": f"https://{slug}.example",
                "industry": _truncate(industry, 120),
                "description": _truncate(
                    f"A mock {niche} brand serving {audience} with a focus on {objective}.", 1000
                ),
                "location": _truncate(location, 120),
                "relevance_score": round(relevance, 1),
                "confidence_score": round(confidence, 1),
                "fit_reasons": [
                    _truncate(f"Aligned with the requested {industry} industry criteria.", 300),
                    _truncate(f"Potential fit for {platform} campaigns targeting {audience}.", 300),
                ],
                "outreach_angle": _truncate(
                    f"Propose a small {platform} creator pilot centered on {objective}.", 500
                ),
                "source_type": "mock",
                "warnings": ["Synthetic mock result; verify all brand details before use."],
            })
        return {"results": results}


class OpenAIBrandDiscoveryProvider(BrandDiscoveryProvider):
    """OpenAI Responses API adapter isolated behind the provider interface."""

    name = "openai"
    is_mock = False

    def __init__(
        self,
        settings: AISettings,
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        settings.validate()
        if settings.mock_mode:
            raise AIConfigurationError("invalid_mock_mode")
        self._api_key = settings.api_key
        self._model = settings.model
        self._timeout_seconds = settings.timeout_seconds
        self._max_output_tokens = settings.max_output_tokens
        self._http_transport = http_transport

    async def generate(self, *, prompt: BrandDiscoveryPrompt, request: BrandDiscoveryRequest) -> ProviderGeneration:
        body = {
            "model": self._model,
            "input": prompt.as_messages(),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "brand_discovery_preview",
                    "strict": True,
                    "schema": response_json_schema(),
                }
            },
            "max_output_tokens": self._max_output_tokens,
            "reasoning": {"effort": "none"},
            "store": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                transport=self._http_transport,
                timeout=httpx.Timeout(self._timeout_seconds),
            ) as client:
                response = await client.post(OPENAI_RESPONSES_URL, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise asyncio.TimeoutError() from exc
        except httpx.RequestError as exc:
            raise RetryableProviderError() from exc

        if response.status_code in RETRYABLE_HTTP_STATUS_CODES:
            raise RetryableProviderError()
        if response.status_code >= 400:
            raise AIProviderUnavailableError()

        try:
            response_data = response.json()
        except ValueError:
            raise AIProviderOutputError() from None
        raw_output = _extract_output_text(response_data)
        usage = response_data.get("usage", {}) if isinstance(response_data, dict) else {}
        input_tokens = _safe_token_count(usage.get("input_tokens"))
        output_tokens = _safe_token_count(usage.get("output_tokens"))
        total_tokens = _safe_token_count(usage.get("total_tokens")) or input_tokens + output_tokens
        return ProviderGeneration(
            raw_output=raw_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


def build_provider(
    settings: AISettings,
    *,
    openai_http_transport: Optional[httpx.AsyncBaseTransport] = None,
) -> BrandDiscoveryProvider:
    settings.validate()
    if settings.mock_mode or settings.provider == "mock":
        return MockBrandDiscoveryProvider()
    if settings.provider == "openai":
        return OpenAIBrandDiscoveryProvider(settings, http_transport=openai_http_transport)
    raise AIConfigurationError()


def _extract_output_text(response_data: Any) -> str:
    if not isinstance(response_data, dict):
        raise AIProviderOutputError()

    direct_output = response_data.get("output_text")
    if isinstance(direct_output, str) and direct_output.strip():
        return direct_output

    for item in response_data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            output_text = content.get("text")
            if content.get("type") == "output_text" and isinstance(output_text, str) and output_text.strip():
                return output_text
    raise AIProviderOutputError()


def response_json_schema() -> dict[str, Any]:
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    result_properties = {
        "brand_name": {"type": "string"},
        "website": nullable_string,
        "industry": {"type": "string"},
        "description": {"type": "string"},
        "location": nullable_string,
        "relevance_score": {"type": "number"},
        "confidence_score": {"type": "number"},
        "fit_reasons": {
            "type": "array", "items": {"type": "string"},
        },
        "outreach_angle": {"type": "string"},
        "source_type": {"type": "string", "enum": ["ai_generated"]},
        "warnings": {
            "type": "array", "items": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(result_properties),
                    "properties": result_properties,
                },
            }
        },
    }


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _safe_token_count(value: Any) -> int:
    if isinstance(value, int) and 0 <= value <= 10_000_000:
        return value
    return 0
