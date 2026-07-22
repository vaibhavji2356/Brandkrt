"""Available-data scoring; absent evidence is omitted instead of scored as zero."""

import math

from brand_discovery_ai.discovery_schemas import NormalizedProfile

from .models import CreatorInsightInput


def _weighted_available(components: list[tuple[float | None, float]]) -> tuple[float | None, float]:
    present = [(value, weight) for value, weight in components if value is not None]
    total_weight = sum(weight for _, weight in components)
    present_weight = sum(weight for _, weight in present)
    if not present or not present_weight:
        return None, 0.0
    return round(sum(value * weight for value, weight in present) / present_weight, 2), present_weight / total_weight


def creator_quality(profile: NormalizedProfile, insight: CreatorInsightInput | None) -> tuple[float | None, float, list[str]]:
    engagement = profile.engagement_rate
    engagement_score = min(100.0, engagement / 8 * 100) if engagement is not None else None
    average_views = insight.average_views if insight and insight.average_views is not None else profile.average_views
    reach_score = min(100.0, math.log10(average_views + 1) / 6 * 100) if average_views is not None else None
    consistency = min(100.0, insight.posting_frequency / 8 * 100) if insight and insight.posting_frequency is not None else None
    verified = 100.0 if profile.verified is True else (50.0 if profile.verified is False else None)
    audience = insight.audience_quality_score if insight else None
    content = insight.content_quality_score if insight else None
    score, coverage = _weighted_available([
        (engagement_score, 0.25), (reach_score, 0.20), (consistency, 0.15),
        (audience, 0.20), (content, 0.15), (verified, 0.05),
    ])
    confidence = round(profile.source_confidence * (0.35 + 0.65 * coverage), 4)
    warnings = [] if coverage >= 0.7 else ["Creator quality is based on partial measurable data."]
    return score, confidence, warnings


def budget_fit(rate: float | None, budget: float, requested_count: int) -> float | None:
    if rate is None:
        return None
    ideal = budget / requested_count
    if rate <= ideal:
        return round(70 + 30 * (rate / ideal), 2)
    return round(max(0.0, 100 - (rate - ideal) / ideal * 100), 2)


def recommendation_score(quality: float | None, research_rank: float | None,
                         budget_score: float | None, roi_score: float | None) -> tuple[float | None, float]:
    return _weighted_available([(quality, 0.35), (research_rank, 0.30), (budget_score, 0.20), (roi_score, 0.15)])
