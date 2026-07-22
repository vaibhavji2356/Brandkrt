"""Campaign-efficiency estimates grounded only in supplied or normalized facts."""

from brand_discovery_ai.discovery_schemas import NormalizedProfile

from .models import CreatorInsightInput, PricingAnalysis, ROIAnalysis


def analyze_roi(profile: NormalizedProfile, insight: CreatorInsightInput | None, pricing: PricingAnalysis) -> ROIAnalysis:
    reach = insight.average_views if insight and insight.average_views is not None else profile.average_views
    likes = insight.average_likes if insight and insight.average_likes is not None else profile.average_likes
    comments = insight.average_comments if insight and insight.average_comments is not None else profile.average_comments
    warnings: list[str] = []
    engagements: int | None = None
    engagement_confidence = 0.0

    if likes is not None or comments is not None:
        engagements = (likes or 0) + (comments or 0)
        engagement_confidence = 0.85
    elif reach is not None and profile.engagement_rate is not None:
        engagements = round(reach * profile.engagement_rate / 100)
        engagement_confidence = 0.55
        warnings.append("Expected engagements are modeled from observed reach and engagement rate.")
    else:
        warnings.append("Expected engagements are unavailable; missing metrics were not fabricated.")

    if reach is None:
        warnings.append("Expected reach is unavailable; follower count was not used as a reach substitute.")

    rate = pricing.selected_rate
    cpe = round(rate / engagements, 4) if rate is not None and engagements and engagements > 0 else None
    cpm = round(rate / reach * 1000, 4) if rate is not None and reach and reach > 0 else None
    efficiency_values = []
    if cpe is not None:
        efficiency_values.append(max(0.0, min(100.0, 100 - cpe * 10)))
    if cpm is not None:
        efficiency_values.append(max(0.0, min(100.0, 100 - cpm * 2)))
    roi_score = round(sum(efficiency_values) / len(efficiency_values), 2) if efficiency_values else None
    if roi_score is None:
        warnings.append("ROI score is unavailable without both a rate and measurable outcome basis.")
    else:
        warnings.append("ROI score is a normalized efficiency estimate, not a revenue or conversion forecast.")

    factual_coverage = sum(value is not None for value in (rate, reach, engagements)) / 3
    confidence = round(min(profile.source_confidence, pricing.price_confidence or 1.0) * factual_coverage * (engagement_confidence or 0.5), 4)
    return ROIAnalysis(
        profile_reference=f"{profile.platform.value}:{profile.platform_id}", expected_reach=reach,
        expected_engagements=engagements, cost_per_engagement=cpe, cpm_reach=cpm,
        roi_score=roi_score, confidence=confidence, warnings=warnings,
    )
