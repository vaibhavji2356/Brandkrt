"""Deterministic recommendations grounded in ranking, confidence and warnings."""

from research_agent.models import RankingSummaryItem, ResearchPackage

from .models import (
    CampaignStrategy, CampaignType, ContentStyle, CreatorRecommendation,
    MarketingIntelligence, OutreachPlan, RecommendationCategory, RecommendationRisk,
)


INSUFFICIENT = "Insufficient verified data."


def deterministic_recommendations(package: ResearchPackage) -> list[CreatorRecommendation]:
    ranking = {item.entity_key: item for item in package.ranking_summary}
    recommendations = []
    for profile in package.normalized_entities:
        if profile.entity_type != "creator":
            continue
        reference = f"{profile.platform.value}:{profile.platform_id}"
        ranked = ranking.get(reference) or RankingSummaryItem(
            entity_key=reference, score=0, components={}, warnings=["Ranking data is unavailable."],
        )
        recommendations.append(_recommend(profile, ranked, package))
    return recommendations


def category_for_score(score: float) -> RecommendationCategory:
    if score >= 85:
        return RecommendationCategory.EXCELLENT
    if score >= 70:
        return RecommendationCategory.STRONG
    if score >= 50:
        return RecommendationCategory.POSSIBLE
    return RecommendationCategory.WEAK


def _recommend(profile, ranked, package) -> CreatorRecommendation:
    category = category_for_score(ranked.score)
    name = profile.display_name or profile.username or "This creator"
    raw_objective = package.request_summary.get("campaign_objective")
    objective = raw_objective if isinstance(raw_objective, str) and raw_objective.strip() else None
    strengths = _strengths(ranked.components)
    weaknesses = _weaknesses(ranked)
    risks = _risks(profile, ranked, package)
    campaign_type = _campaign_type(objective)
    content_style = _content_style(profile.platform.value, profile.categories)
    niche_fit = _fit_text(ranked.components.get("category_relevance"), "Verified category signals align with the requested niche.", "Verified category signals show limited niche alignment.")
    platform_fit = _fit_text(ranked.components.get("platform_preference"), "The creator is present on a requested campaign platform.", "The platform preference signal is weak.")
    campaign_fit = (
        f"The available profile signals can support planning for {objective}."
        if objective else INSUFFICIENT
    )
    audience_fit = (
        "Verified audience demographics are available for campaign review."
        if profile.audience_demographics else INSUFFICIENT
    )
    summary = f"{name} is a {category.value.lower()} based on deterministic fit signals and source confidence."
    return CreatorRecommendation(
        profile_reference=f"{profile.platform.value}:{profile.platform_id}",
        overall_match_score=round(max(0, min(100, ranked.score)), 2),
        ai_confidence=round(package.confidence * 100, 2),
        recommendation_category=category,
        recommendation_summary=summary,
        why_recommended=[_why(ranked), "The recommendation uses validated profile facts and deterministic ranking only."],
        strengths=strengths, weaknesses=weaknesses,
        campaign_fit=campaign_fit, audience_fit=audience_fit,
        niche_fit=niche_fit, budget_fit=INSUFFICIENT, platform_fit=platform_fit,
        marketing_intelligence=MarketingIntelligence(
            target_audience_overlap=audience_fit,
            brand_positioning_compatibility=niche_fit,
            expected_campaign_style=f"A {content_style.value.lower()} concept is a strategy suggestion to validate with the creator.",
            estimated_collaboration_quality="Use a scoped pilot and agreed success criteria before estimating collaboration quality.",
            long_term_partnership_potential="Evaluate consistency, delivery quality, and campaign results after an initial collaboration.",
        ),
        campaign_strategy=CampaignStrategy(
            campaign_type=campaign_type,
            campaign_goal=objective or "Validate creator-brand fit with measurable campaign objectives.",
            content_style=content_style,
        ),
        outreach=OutreachPlan(
            first_contact_angle=f"Reference {name}'s relevant content focus and propose a clearly scoped collaboration.",
            collaboration_pitch=f"Invite {name} to review a {campaign_type.value.lower()} brief with defined deliverables and creative input.",
            value_proposition="Offer a transparent brief, fair scope, creative clarity, and measurable mutual value.",
            call_to_action="Ask whether the creator is open to reviewing a concise campaign brief and availability window.",
        ),
        risks=risks,
    )


def _strengths(components):
    labels = {
        "category_relevance": "Strong category relevance in the deterministic ranking.",
        "keyword_relevance": "Strong keyword relevance in validated profile content.",
        "location_match": "Location aligns with the requested criteria.",
        "language_match": "Language aligns with the requested criteria.",
        "platform_preference": "Platform aligns with the requested criteria.",
        "source_confidence": "Source confidence is strong.",
    }
    values = [labels[key] for key, value in components.items() if key in labels and value is not None and value >= 75]
    return values[:5] or ["The profile has enough validated data for deterministic evaluation."]


def _weaknesses(ranked):
    values = []
    for key, value in ranked.components.items():
        if value is not None and value < 50:
            values.append(f"The {key.replace('_', ' ')} signal is weak.")
    values.extend(ranked.warnings[:2])
    return list(dict.fromkeys(values))[:5] or ["Some campaign-specific evidence still requires direct creator confirmation."]


def _risks(profile, ranked, package):
    risks = []
    components = ranked.components
    checks = [
        ("audience mismatch", profile.audience_demographics is None, "Audience overlap cannot be verified from available demographics."),
        ("language mismatch", components.get("language_match") is not None and components.get("language_match", 100) < 50, "The validated language signal does not align with the request."),
        ("weak niche alignment", components.get("category_relevance") is not None and components.get("category_relevance", 100) < 50, "The deterministic category relevance signal is weak."),
        ("budget mismatch", True, "Creator pricing is unavailable, so budget fit cannot be verified."),
        ("low confidence", package.confidence < 0.6, "Aggregate factual source confidence is low."),
        ("platform limitations", bool(profile.warnings), "Platform availability or source warnings may limit evaluation."),
        ("missing metrics", any(value is None for value in [profile.follower_count, profile.engagement_rate]), "One or more measurable platform metrics are unavailable."),
        ("insufficient information", bool(package.missing_information), "The research package identifies factual information gaps that require verification."),
    ]
    for risk_type, applies, explanation in checks:
        if applies:
            risks.append(RecommendationRisk(risk_type=risk_type, explanation=explanation))
    if not risks:
        risks.append(RecommendationRisk(risk_type="insufficient information", explanation="Campaign execution details still require direct confirmation."))
    return risks[:8]


def _why(ranked):
    return f"The deterministic ranking score is {ranked.score:.2f} out of 100 using available normalized data."


def _fit_text(value, positive, negative):
    if value is None:
        return INSUFFICIENT
    return positive if value >= 50 else negative


def _campaign_type(objective):
    value = (objective or "").casefold()
    mappings = [
        (("launch", "release"), CampaignType.PRODUCT_LAUNCH),
        (("ugc", "user-generated"), CampaignType.UGC),
        (("giveaway", "contest"), CampaignType.GIVEAWAY),
        (("affiliate", "conversion", "sales"), CampaignType.AFFILIATE),
        (("review",), CampaignType.REVIEW),
        (("ambassador", "long-term"), CampaignType.BRAND_AMBASSADOR),
        (("season", "festival", "holiday"), CampaignType.SEASONAL),
    ]
    return next((kind for terms, kind in mappings if any(term in value for term in terms)), CampaignType.AWARENESS)


def _content_style(platform, categories):
    category_text = " ".join(categories).casefold()
    if "education" in category_text or "technology" in category_text:
        return ContentStyle.EDUCATIONAL
    if platform == "youtube":
        return ContentStyle.LONG_FORM
    if platform in {"instagram", "snapchat"}:
        return ContentStyle.SHORTS
    return ContentStyle.LIFESTYLE
