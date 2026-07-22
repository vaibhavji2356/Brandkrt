"""Creator intelligence orchestration without network, persistence, or AI metric generation."""

from statistics import fmean

from .models import (
    BudgetAnalysis, CampaignObjective, CreatorInsightInput, CreatorIntelligenceRequest,
    CreatorIntelligenceResponse, CreatorMetrics, RecommendationExplanation,
    RecommendedCreator, ROIAnalysis,
)
from .optimizer import PortfolioCandidate, select_portfolio
from .pricing import analyze_pricing
from .roi import analyze_roi
from .scoring import budget_fit, creator_quality, recommendation_score


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _objective_strength(objective: CampaignObjective) -> str:
    return {
        CampaignObjective.AWARENESS: "Measurable reach and category fit support awareness planning.",
        CampaignObjective.APP_INSTALL: "Engagement efficiency can support a testable install campaign, but conversion remains unverified.",
        CampaignObjective.SALES: "Efficiency signals support evaluation, while sales conversion must be validated separately.",
        CampaignObjective.GAMING_LAUNCH: "Platform, reach, and engagement evidence can support a gaming launch pilot.",
        CampaignObjective.PRODUCT_REVIEW: "Content quality and measurable engagement can support a structured product review.",
    }[objective]


def _explanation(objective: CampaignObjective, selected: bool, quality: float | None,
                 budget_score: float | None, pricing_type: str | None,
                 roi_score: float | None, warnings: list[str]) -> RecommendationExplanation:
    why = [_objective_strength(objective)]
    if quality is not None:
        why.append(f"Available-data creator quality score is {quality:.1f}/100.")
    strengths = []
    if budget_score is not None and budget_score >= 70:
        strengths.append("The selected rate is compatible with the per-creator budget target.")
    if roi_score is not None:
        strengths.append("Observed metrics support a normalized efficiency comparison.")
    if not strengths:
        strengths.append("The creator remains comparable on the factual signals currently available.")
    weaknesses = ["Missing measurements reduce confidence rather than being treated as zero quality."] if warnings else ["Campaign outcomes still require measurement after launch."]
    pricing_concerns = []
    if pricing_type == "estimated":
        pricing_concerns.append("The rate is estimated and must be confirmed before contracting.")
    elif pricing_type is None:
        pricing_concerns.append("No usable price is available, so this creator cannot enter the funded portfolio.")
    else:
        pricing_concerns.append("Confirm deliverables, usage rights, and final commercial terms before contracting.")
    budget_text = "Included in the recommended budget portfolio." if selected else "Not included in the current budget-optimal portfolio."
    risks = _unique(warnings[:3] + ["Revenue, conversions, and guaranteed outcomes are not inferred."])
    return RecommendationExplanation(
        why_recommended=why, strengths=strengths, weaknesses=weaknesses,
        pricing_concerns=pricing_concerns, budget_fit=budget_text, risks=risks,
    )


class CreatorIntelligenceEngine:
    def recommend(self, request: CreatorIntelligenceRequest) -> CreatorIntelligenceResponse:
        package = request.research_package
        insights = {item.profile_reference.casefold(): item for item in request.creator_inputs}
        ranking = {item.entity_key.casefold(): item.score for item in package.ranking_summary}
        rows: list[dict] = []
        warnings = list(package.warnings)

        creator_refs = {
            f"{profile.platform.value}:{profile.platform_id}".casefold()
            for profile in package.normalized_entities if profile.entity_type == "creator"
        }
        for unknown in sorted(set(insights) - creator_refs):
            warnings.append(f"Creator input {unknown} was ignored because it is not in the research package.")

        for profile in package.normalized_entities:
            if profile.entity_type != "creator":
                warnings.append(f"Non-creator profile {profile.platform.value}:{profile.platform_id} was excluded.")
                continue
            reference = f"{profile.platform.value}:{profile.platform_id}"
            insight: CreatorInsightInput | None = insights.get(reference.casefold())
            pricing = analyze_pricing(profile, insight, request.currency)
            roi = analyze_roi(profile, insight, pricing)
            quality, quality_confidence, quality_warnings = creator_quality(profile, insight)
            budget_score = budget_fit(pricing.selected_rate, request.campaign_budget, request.number_of_creators)
            score, score_coverage = recommendation_score(quality, ranking.get(reference.casefold()), budget_score, roi.roi_score)
            average_views = insight.average_views if insight and insight.average_views is not None else profile.average_views
            average_likes = insight.average_likes if insight and insight.average_likes is not None else profile.average_likes
            average_comments = insight.average_comments if insight and insight.average_comments is not None else profile.average_comments
            confidence = round(min(1.0, fmean([quality_confidence, pricing.price_confidence, roi.confidence, package.confidence]) * (0.5 + 0.5 * score_coverage)), 4)
            row_warnings = _unique(profile.warnings + quality_warnings + roi.warnings)
            rows.append({
                "profile": profile, "reference": reference, "pricing": pricing, "roi": roi,
                "quality": quality, "budget_score": budget_score, "score": score,
                "average_views": average_views, "average_likes": average_likes,
                "average_comments": average_comments, "insight": insight,
                "confidence": confidence, "warnings": row_warnings,
            })

        candidates = [PortfolioCandidate(
            reference=row["reference"], rate=row["pricing"].selected_rate,
            score=row["score"] or 0.0, reach=row["roi"].expected_reach,
        ) for row in rows if row["pricing"].selected_rate is not None]
        selected_refs = set(select_portfolio(candidates, request.campaign_budget, request.number_of_creators))
        ordered = sorted(rows, key=lambda row: (-(row["score"] if row["score"] is not None else -1), row["reference"]))
        recommendations: list[RecommendedCreator] = []
        for rank_position, row in enumerate(ordered, 1):
            profile, pricing, roi = row["profile"], row["pricing"], row["roi"]
            selected = row["reference"] in selected_refs
            insight = row["insight"]
            metrics = CreatorMetrics(
                profile_reference=row["reference"], estimated_rate=pricing.estimated_rate,
                negotiated_rate=pricing.negotiated_rate, currency=pricing.currency,
                price_confidence=pricing.price_confidence, engagement_rate=profile.engagement_rate,
                average_views=row["average_views"], average_likes=row["average_likes"],
                average_comments=row["average_comments"],
                posting_frequency=insight.posting_frequency if insight else None,
                audience_quality_score=insight.audience_quality_score if insight else None,
                creator_quality_score=row["quality"], cost_per_engagement=roi.cost_per_engagement,
                cpm_reach=roi.cpm_reach, roi_score=roi.roi_score,
                budget_fit_score=row["budget_score"],
                recommendation_score=round(row["score"], 2) if row["score"] is not None else None,
                pricing_notes=pricing.pricing_notes, confidence=row["confidence"],
            )
            recommendations.append(RecommendedCreator(
                profile_reference=row["reference"], platform=profile.platform.value,
                username=profile.username, selected=selected, rank=rank_position,
                metrics=metrics, pricing=pricing, roi=roi,
                explanation=_explanation(request.campaign_objective, selected, row["quality"],
                                         row["budget_score"], pricing.rate_type, roi.roi_score,
                                         row["warnings"]), warnings=row["warnings"],
            ))

        selected = [item for item in recommendations if item.selected]
        spend = round(sum(item.pricing.selected_rate or 0 for item in selected), 2)
        all_reach_known = bool(selected) and all(item.roi.expected_reach is not None for item in selected)
        all_engagement_known = bool(selected) and all(item.roi.expected_engagements is not None for item in selected)
        reach = sum(item.roi.expected_reach or 0 for item in selected) if all_reach_known else None
        engagements = sum(item.roi.expected_engagements or 0 for item in selected) if all_engagement_known else None
        budget_warnings: list[str] = []
        if len(selected) < request.number_of_creators:
            budget_warnings.append("The requested creator count could not be fully funded from available priced candidates.")
        if selected and not all_reach_known:
            budget_warnings.append("Portfolio reach is unavailable because one or more selected creators lack observed average views.")
        if not selected:
            budget_warnings.append("No priced creator fits within the campaign budget.")
        minimum_met = None if request.minimum_reach is None or reach is None else reach >= request.minimum_reach
        if minimum_met is False:
            budget_warnings.append("The selected portfolio does not meet the requested minimum reach.")
        budget_confidence = round(fmean([item.metrics.confidence for item in selected]), 4) if selected else 0.0
        budget_analysis = BudgetAnalysis(
            campaign_budget=request.campaign_budget, expected_spend=spend,
            remaining_budget=round(request.campaign_budget - spend, 2),
            budget_utilization=round(spend / request.campaign_budget * 100, 2),
            selected_creator_count=len(selected), requested_creator_count=request.number_of_creators,
            expected_reach=reach, expected_engagements=engagements,
            minimum_reach_met=minimum_met, confidence=budget_confidence, warnings=budget_warnings,
        )
        aggregate_cpe = round(spend / engagements, 4) if engagements else None
        aggregate_cpm = round(spend / reach * 1000, 4) if reach else None
        roi_values = [item.roi.roi_score for item in selected if item.roi.roi_score is not None]
        aggregate_roi = ROIAnalysis(
            expected_reach=reach, expected_engagements=engagements,
            cost_per_engagement=aggregate_cpe, cpm_reach=aggregate_cpm,
            roi_score=round(fmean(roi_values), 2) if roi_values else None,
            confidence=budget_confidence,
            warnings=_unique([warning for item in selected for warning in item.roi.warnings] + budget_warnings),
        )
        all_warnings = _unique(warnings + budget_warnings + [
            "Pricing and ROI outputs are estimates unless explicitly marked as verified.",
            "No recommendation is a guarantee of reach, engagement, conversion, or revenue.",
        ])
        return CreatorIntelligenceResponse(
            recommendations=recommendations,
            ranking=[item.profile_reference for item in recommendations],
            pricing_analysis=[item.pricing for item in recommendations],
            budget_analysis=budget_analysis, roi_analysis=aggregate_roi,
            confidence=budget_confidence, reasoning_source="deterministic_creator_intelligence",
            warnings=all_warnings,
        )
