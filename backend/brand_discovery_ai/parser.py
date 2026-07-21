"""Strict parsing boundary for untrusted provider responses."""

import json
import ipaddress
import re
from typing import Any

from pydantic import ValidationError

from .errors import AIProviderOutputError
from .schemas import BrandDiscoveryResult, ProviderPayload


MAX_PROVIDER_RESPONSE_CHARS = 250_000


PLACEHOLDER_PATTERNS = (
    "lorem ipsum", "placeholder", "example brand", "test brand", "sample brand",
    "to be determined", "tbd", "n/a",
)
FABRICATED_SOURCE_PATTERNS = (
    "verified via", "confirmed by official", "sourced from live", "based on web research",
    "scraped from", "checked against official", "independently confirmed",
    "externally verified", "independently verified", "officially verified",
)


def parse_provider_output(
    raw: Any,
    *,
    result_limit: int,
    provider_name: str = "",
) -> list[BrandDiscoveryResult]:
    try:
        if isinstance(raw, str):
            if len(raw) > MAX_PROVIDER_RESPONSE_CHARS:
                raise AIProviderOutputError()
            decoded = json.loads(raw)
        elif isinstance(raw, dict):
            decoded = raw
        else:
            raise AIProviderOutputError()

        payload = ProviderPayload.model_validate(decoded)
        results = payload.results[:result_limit]
        _validate_quality(results, provider_name=provider_name)
        return results
    except AIProviderOutputError:
        raise
    except (json.JSONDecodeError, TypeError, ValidationError, ValueError):
        raise AIProviderOutputError() from None


def _validate_quality(results: list[BrandDiscoveryResult], *, provider_name: str) -> None:
    seen_brands: set[str] = set()
    required_source_type = "mock" if provider_name == "mock" else "ai_generated"

    for result in results:
        brand_key = re.sub(r"[^a-z0-9]+", "", result.brand_name.casefold())
        if not brand_key or brand_key in seen_brands:
            raise AIProviderOutputError()
        seen_brands.add(brand_key)

        if result.source_type != required_source_type:
            raise AIProviderOutputError()
        if len(result.warnings) > 4:
            raise AIProviderOutputError()
        if result.relevance_score >= 90 and result.confidence_score <= 10:
            raise AIProviderOutputError()

        text_values = [
            result.brand_name,
            result.description,
            result.outreach_angle,
            *result.fit_reasons,
            *result.warnings,
        ]
        normalized_text = " ".join(text_values).casefold()
        if any(pattern in normalized_text for pattern in PLACEHOLDER_PATTERNS):
            raise AIProviderOutputError()
        claim_text = normalized_text.replace("not externally verified", "").replace(
            "not independently verified", ""
        )
        if any(pattern in claim_text for pattern in FABRICATED_SOURCE_PATTERNS):
            raise AIProviderOutputError()

        if result.website is not None:
            _validate_website(result.website, provider_name=provider_name)


def _validate_website(website, *, provider_name: str) -> None:
    if website.scheme != "https" or website.username or website.password:
        raise AIProviderOutputError()
    host = (website.host or "").rstrip(".").casefold()
    if not host or host == "localhost" or host.endswith((".localhost", ".local")):
        raise AIProviderOutputError()
    if provider_name != "mock" and host.endswith((".example", ".invalid", ".test")):
        raise AIProviderOutputError()
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        if "." not in host:
            raise AIProviderOutputError() from None
    else:
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise AIProviderOutputError()
