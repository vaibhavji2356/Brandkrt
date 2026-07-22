"""Deterministic validation of structured narrative against authoritative results."""

import math
import re
from typing import Any

from .models import CreatorIntelligenceResponse, PortfolioNarrative


class NarrativeGroundingError(ValueError):
    pass


_NUMBER = re.compile(r"(?<![A-Za-z0-9_-])-?\d[\d,]*(?:\.\d+)?%?")
_CURRENCIES = frozenset({"USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY", "CNY", "AED", "SGD"})
_UNSAFE_PATTERNS = (
    r"\bare\s+guaranteed\b(?![^.]{0,80}\b(?:not|never)\b)", r"\bguarantees\b",
    r"\b(?:we|creator|portfolio|campaign)\s+guarantee\b",
    r"\bassured\b", r"\bwill\s+(?:deliver|achieve|generate|produce)\b",
    r"\bfollowers?\s+(?:equal|equals|are|is|become|represent)\s+(?:the\s+)?reach\b",
    r"\bestimat(?:e|ed|es)\s+(?:is|are|was|were)\s+(?:a\s+)?verified\b",
    r"\bverified\s+fact\b.{0,30}\bestimat(?:e|ed|es)\b",
    r"\b(?:expected|forecast|projected|will generate)\s+(?:revenue|sales|conversions?|installs?)\b",
    r"\b(?:age distribution|gender split|audience demographics?|household income)\b",
    r"<[^>]+>", r"\[[^\]]+\]\([^)]+\)",
)


def validate_narrative(narrative: PortfolioNarrative, source: CreatorIntelligenceResponse) -> None:
    expected = source.ranking
    actual = [item.profile_reference for item in narrative.creator_narratives]
    if actual != expected:
        raise NarrativeGroundingError("creator ranking mismatch")

    source_by_ref = {item.profile_reference: item for item in source.recommendations}
    for item in narrative.creator_narratives:
        creator = source_by_ref.get(item.profile_reference)
        if creator is None:
            raise NarrativeGroundingError("unknown creator reference")
        platform_id = item.profile_reference.split(":", 1)[1] if ":" in item.profile_reference else ""
        if item.platform != creator.platform or item.platform_id != platform_id or item.username != creator.username:
            raise NarrativeGroundingError("creator identity mismatch")
        creator_text = " ".join(_descriptive_text(item.model_dump()))
        if "verified" in creator_text.casefold() and not creator.pricing.verified_rate_preserved:
            raise NarrativeGroundingError("unsupported verified-rate claim")
        _validate_numbers(item.pricing_assessment, _numeric_values(creator.pricing.model_dump()))
        _validate_numbers(item.negotiation_guidance, _numeric_values(creator.pricing.model_dump()))
        other_creator_text = " ".join([
            item.selection_reason, *item.strengths, *item.weaknesses,
            item.uncertainty, *item.risk_flags,
        ])
        _validate_numbers(other_creator_text, _numeric_values(creator.model_dump()))

    all_text = " ".join(_descriptive_text(narrative.model_dump()))
    folded = all_text.casefold()
    for pattern in _UNSAFE_PATTERNS:
        if re.search(pattern, folded, flags=re.IGNORECASE | re.DOTALL):
            raise NarrativeGroundingError("unsupported narrative claim")

    _validate_numbers(narrative.budget_assessment, _numeric_values(source.budget_analysis.model_dump()))
    _validate_numbers(narrative.confidence_statement, [source.confidence, source.budget_analysis.confidence])
    _validate_numbers(narrative.expected_efficiency_summary, _numeric_values(source.roi_analysis.model_dump()))
    other_portfolio_text = " ".join([
        narrative.executive_summary, narrative.objective_alignment,
        *narrative.portfolio_tradeoffs, *narrative.risk_summary,
        *narrative.recommended_actions, *narrative.warnings,
    ])
    _validate_numbers(other_portfolio_text, _numeric_values(source.model_dump(exclude={"ai_narrative"})))

    used_currencies = {token for token in re.findall(r"\b[A-Z]{3}\b", all_text) if token in _CURRENCIES}
    allowed_currencies = {item.pricing.currency for item in source.recommendations}
    if not used_currencies.issubset(allowed_currencies):
        raise NarrativeGroundingError("currency mismatch")


def _validate_numbers(text: str, allowed_numbers: list[float]) -> None:
    for match in _NUMBER.finditer(text):
        raw = match.group(0)
        percent = raw.endswith("%")
        try:
            value = float(raw.rstrip("%").replace(",", ""))
        except ValueError:
            raise NarrativeGroundingError("invalid numeric claim") from None
        candidates = [value, value / 100 if percent else value]
        if not any(any(math.isclose(candidate, allowed, rel_tol=0, abs_tol=0.01) for allowed in allowed_numbers) for candidate in candidates):
            raise NarrativeGroundingError("unsupported numeric claim")


def _descriptive_text(value: Any, key: str | None = None) -> list[str]:
    identity_keys = {"profile_reference", "platform", "platform_id", "username"}
    if isinstance(value, str):
        return [] if key in identity_keys else [value]
    if isinstance(value, dict):
        result: list[str] = []
        for child_key, child in value.items():
            result.extend(_descriptive_text(child, child_key))
        return result
    if isinstance(value, list):
        return [text for child in value for text in _descriptive_text(child, key)]
    return []


def _numeric_values(value: Any) -> list[float]:
    values: list[float] = []
    if isinstance(value, bool):
        return values
    if isinstance(value, (int, float)) and math.isfinite(value):
        values.append(float(value))
    elif isinstance(value, dict):
        for child in value.values():
            values.extend(_numeric_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_numeric_values(child))
    return values
