"""Deterministic pricing selection with verified-rate protection."""

from brand_discovery_ai.discovery_schemas import NormalizedProfile

from .models import CreatorInsightInput, PriceRange, PricingAnalysis


_PLATFORM_CPM = {"youtube": 28.0, "twitch": 24.0, "x": 16.0, "instagram": 22.0, "snapchat": 18.0}


def _money(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def analyze_pricing(profile: NormalizedProfile, insight: CreatorInsightInput | None, currency: str) -> PricingAnalysis:
    supplied = insight.pricing if insight else None
    notes = list(supplied.pricing_notes if supplied else [])
    average_views = (insight.average_views if insight and insight.average_views is not None else profile.average_views)
    model_estimate: float | None = None
    model_confidence = 0.0
    model_source: str | None = None

    if average_views is not None and average_views > 0:
        model_estimate = max(25.0, average_views / 1000 * _PLATFORM_CPM.get(profile.platform.value, 20.0))
        model_confidence = 0.58
        model_source = "deterministic_average_views_benchmark"
        notes.append("Estimate uses observed average views and a documented platform benchmark; it is not a quoted rate.")
    elif profile.follower_count is not None and profile.follower_count > 0:
        model_estimate = max(25.0, profile.follower_count / 1000 * _PLATFORM_CPM.get(profile.platform.value, 20.0) * 0.12)
        model_confidence = 0.35
        model_source = "deterministic_follower_benchmark"
        notes.append("Low-confidence estimate uses follower count because observed average views are unavailable.")

    selected: float | None = None
    rate_type: str | None = None
    source: str | None = None
    confidence = 0.0
    manual_applied = False
    verified_preserved = False
    estimated = supplied.estimated_rate if supplied and supplied.estimated_rate is not None else model_estimate

    # Verified commercial facts always win, including over a manual override.
    if supplied and supplied.negotiated_rate is not None and supplied.negotiated_rate_verified:
        selected, rate_type = supplied.negotiated_rate, "verified_negotiated"
        source, confidence, verified_preserved = supplied.pricing_source or "verified_negotiation", supplied.price_confidence or 0.98, True
    elif supplied and supplied.known_rate is not None and supplied.known_rate_verified:
        selected, rate_type = supplied.known_rate, "verified_known"
        source, confidence, verified_preserved = supplied.pricing_source or "verified_rate", supplied.price_confidence or 0.95, True
    elif supplied and supplied.manual_rate_override is not None:
        selected, rate_type, manual_applied = supplied.manual_rate_override, "manual_override", True
        source, confidence = supplied.pricing_source or "manual_override", supplied.price_confidence or 0.75
    elif supplied and supplied.negotiated_rate is not None:
        selected, rate_type = supplied.negotiated_rate, "unverified_negotiated"
        source, confidence = supplied.pricing_source or "unverified_negotiation", supplied.price_confidence or 0.7
    elif supplied and supplied.known_rate is not None:
        selected, rate_type = supplied.known_rate, "unverified_known"
        source, confidence = supplied.pricing_source or "unverified_rate", supplied.price_confidence or 0.65
    elif estimated is not None:
        selected, rate_type = estimated, "estimated"
        source = (supplied.pricing_source if supplied and supplied.estimated_rate is not None else model_source) or "caller_estimate"
        confidence = (supplied.price_confidence if supplied and supplied.price_confidence is not None else model_confidence or 0.5)
    else:
        notes.append("No legitimate rate or sufficient pricing basis is available.")

    if verified_preserved and supplied and supplied.manual_rate_override is not None:
        notes.append("Manual override was ignored to preserve the verified rate.")

    explicit_range = supplied.price_range if supplied else None
    negotiation_range = explicit_range
    if negotiation_range is None and selected is not None:
        negotiation_range = PriceRange(minimum=_money(selected * 0.85), maximum=_money(selected * 1.15))

    return PricingAnalysis(
        profile_reference=f"{profile.platform.value}:{profile.platform_id}",
        selected_rate=_money(selected), estimated_rate=_money(estimated),
        negotiated_rate=_money(supplied.negotiated_rate) if supplied else None,
        currency=(insight.currency if insight and insight.currency else currency), rate_type=rate_type,
        expected_negotiation_range=negotiation_range, price_confidence=round(min(1.0, confidence), 4),
        pricing_source=source, manual_override_applied=manual_applied,
        verified_rate_preserved=verified_preserved, pricing_notes=list(dict.fromkeys(notes)),
    )
