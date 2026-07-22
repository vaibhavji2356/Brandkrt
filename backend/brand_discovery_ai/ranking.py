"""Deterministic ranking over normalized factual fields only."""

from .discovery_schemas import DiscoveryCriteria, NormalizedProfile, RankedProfile, RankingBreakdown


WEIGHTS = {
    "category_relevance": 18, "keyword_relevance": 16, "location_match": 10,
    "language_match": 8, "platform_preference": 8, "follower_range_match": 12,
    "engagement_match": 12, "data_completeness": 8, "source_confidence": 8,
}


def rank_profile(profile: NormalizedProfile, criteria: DiscoveryCriteria) -> RankedProfile:
    requested_categories = {v.casefold() for v in [criteria.niche, *criteria.categories] if v}
    actual_categories = {v.casefold() for v in profile.categories}
    category = _overlap(requested_categories, actual_categories)
    requested_keywords = {v.casefold() for v in criteria.keywords}
    actual_text = " ".join([profile.biography or "", *profile.keywords]).casefold()
    keyword = sum(term in actual_text for term in requested_keywords) / len(requested_keywords) if requested_keywords else 1.0
    location = _text_match(criteria.location, profile.location)
    language = _text_match(criteria.language, profile.language)
    platform = 1.0 if profile.platform in criteria.platforms else 0.0
    follower = _range_match(profile.follower_count, criteria.minimum_followers, criteria.maximum_followers)
    engagement = None if profile.engagement_rate is None or criteria.minimum_engagement_rate is None else (1.0 if profile.engagement_rate >= criteria.minimum_engagement_rate else max(0.0, profile.engagement_rate / criteria.minimum_engagement_rate))
    completeness_fields = [profile.display_name, profile.biography, profile.location, profile.language, profile.follower_count, profile.content_count, profile.engagement_rate, profile.verified, profile.website]
    completeness = sum(value is not None for value in completeness_fields) / len(completeness_fields)
    values = {"category_relevance": category, "keyword_relevance": keyword, "location_match": location, "language_match": language, "platform_preference": platform, "follower_range_match": follower, "engagement_match": engagement, "data_completeness": completeness, "source_confidence": profile.source_confidence}
    applicable = {name: value for name, value in values.items() if value is not None}
    score = 100 * sum(WEIGHTS[name] * value for name, value in applicable.items()) / sum(WEIGHTS[name] for name in applicable)
    warnings = list(profile.warnings)
    if follower is None and (criteria.minimum_followers is not None or criteria.maximum_followers is not None):
        warnings.append("Follower-range fit not scored because follower_count is unavailable.")
    if engagement is None and criteria.minimum_engagement_rate is not None:
        warnings.append("Engagement fit not scored because engagement_rate is unavailable.")
    return RankedProfile(profile=profile, score=round(score, 2), score_components=RankingBreakdown(**{k: (None if v is None else round(v * 100, 2)) for k, v in values.items()}), warnings=list(dict.fromkeys(warnings)))


def rank_profiles(profiles: list[NormalizedProfile], criteria: DiscoveryCriteria) -> list[RankedProfile]:
    ranked = [rank_profile(profile, criteria) for profile in profiles]
    return sorted(ranked, key=lambda item: (-item.score, item.profile.platform.value, item.profile.platform_id))


def _overlap(requested: set[str], actual: set[str]) -> float:
    return len(requested & actual) / len(requested) if requested else 1.0


def _text_match(requested: str | None, actual: str | None) -> float | None:
    if requested is None:
        return 1.0
    if actual is None:
        return None
    return 1.0 if requested.casefold() in actual.casefold() else 0.0


def _range_match(value: int | None, minimum: int | None, maximum: int | None) -> float | None:
    if minimum is None and maximum is None:
        return 1.0
    if value is None:
        return None
    if minimum is not None and value < minimum:
        return max(0.0, value / minimum) if minimum else 0.0
    if maximum is not None and value > maximum:
        return max(0.0, maximum / value)
    return 1.0
