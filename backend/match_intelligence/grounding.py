"""Post-validation that rejects ungrounded protected factual claims."""

import re

from .models import ProviderPayload


NUMERIC_METRIC = re.compile(
    r"(?:\b\d[\d,.]*\s*(?:thousand|million|billion|k|m)?\s*%?\s*(?:followers?|subscribers?|views?|likes?|comments?)\b|"
    r"\bengagement(?:\s+rate)?\s*(?:is|of|:)?\s*\d)", re.IGNORECASE,
)
IDENTITY_CLAIM = re.compile(
    r"\b(?:is|as)\s+(?:a\s+)?verified\b|\bverified\s+(?:creator|channel|account)\b|"
    r"\b(?:official|confirmed)\s+website\b",
    re.IGNORECASE,
)
PROTECTED_FACT_TERM = re.compile(
    r"\b(?:followers?|subscribers?|view\s+count|verified|verification|country|official\s+website)\b|"
    r"\b(?:based|located)\s+in\b",
    re.IGNORECASE,
)


class GroundingError(ValueError):
    pass


def validate_provider_payload(payload: ProviderPayload, expected_references: list[str]) -> None:
    references = [item.profile_reference for item in payload.recommendations]
    if len(references) != len(set(references)) or set(references) != set(expected_references):
        raise GroundingError("Provider profile references do not match factual context.")
    seen_text = set()
    for recommendation in payload.recommendations:
        for text in _text_values(recommendation.model_dump(mode="json")):
            key = re.sub(r"\s+", " ", text).strip().casefold()
            if key != "insufficient verified data." and (
                NUMERIC_METRIC.search(text) or IDENTITY_CLAIM.search(text) or PROTECTED_FACT_TERM.search(text)
            ):
                raise GroundingError("Provider output contains a protected factual claim.")
            if key != "insufficient verified data." and len(key) >= 24 and key in seen_text:
                raise GroundingError("Provider output repeats reasoning.")
            seen_text.add(key)


def _text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _text_values(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key not in {"profile_reference", "risk_type"}:
                yield from _text_values(item)
