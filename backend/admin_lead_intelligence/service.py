"""Admin lead research orchestration with factual grounding and safe degradation."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from urllib.parse import urlsplit

from fastapi import HTTPException

from brand_discovery_ai.discovery_schemas import NormalizedProfile
from brand_discovery_ai.usage import UsageIdentity
from creator_intelligence.models import CreatorInsightInput
from creator_intelligence.pricing import analyze_pricing
from match_intelligence.engine import MatchEngine
from operations.metrics import operational_metrics
from research_agent.agent import ResearchAgent

from .models import (
    AIActivityPage, AdminResearchRequest, AuditEvent, CommercialSummary,
    GroundedAssistance, LeadAnalytics, LeadIntelligenceResult, LeadNoteRequest,
    LeadPriority, LeadStatus, LeadUpdateRequest, PricingSummary, PriorityScore,
    ResearchHistoryPage, ResearchJobDetail, ResearchJobStatus, ResearchJobSummary,
    SaveLeadRequest, SavedLead, SavedLeadPage,
)
from .repository import AdminLeadRepository


logger = logging.getLogger("brandkrt.admin_lead_intelligence")


class AdminLeadService:
    def __init__(
        self, repository: AdminLeadRepository, research_agent: ResearchAgent,
        match_engine: MatchEngine | None = None,
    ):
        self.repository = repository
        self.research_agent = research_agent
        self.match_engine = match_engine or MatchEngine()

    async def create_job(self, request: AdminResearchRequest, user: dict) -> ResearchJobSummary:
        actor_id = str(user.get("_id", "unknown"))
        await self.repository.fail_stale_jobs(actor_id)
        if await self.repository.active_job_count(actor_id) >= 3:
            raise HTTPException(status_code=409, detail="Complete an active research job before starting another.")
        document = await self.repository.create_job(request, actor_id)
        operational_metrics.increment("admin_research_jobs_created")
        return _job_summary(document)

    async def run_job(
        self, job_id: str, request: AdminResearchRequest, user: dict,
        usage_identity: UsageIdentity,
    ) -> None:
        actor_id = str(user.get("_id", "unknown"))
        now = datetime.now(timezone.utc)
        await self.repository.update_job(job_id, {
            "status": ResearchJobStatus.RUNNING.value, "progress": 10,
            "started_at": now, "error_code": None,
        })
        try:
            run = await self.research_agent.research(request.discovery_criteria())
            await self.repository.update_job(job_id, {"progress": 65})
            package = run.package
            match = await self.match_engine.recommend(package, usage_identity=usage_identity)
            recommendations = {item.profile_reference: item for item in match.recommendations}
            ranking = {item.entity_key: item for item in package.ranking_summary}
            duplicates = _duplicate_map(package.identity_suggestions)
            results = []
            extra_warnings: list[str] = []
            budget_excluded = 0
            budget_unavailable = 0
            if request.minimum_audience_quality is not None:
                extra_warnings.append(
                    "Audience-quality filtering was not applied where an official quality measurement was unavailable."
                )
            for profile in package.normalized_entities:
                entity_key = f"{profile.platform.value}:{profile.platform_id}"
                ranked = ranking.get(entity_key)
                commercial = await self.repository.commercial_summary(
                    profile.platform.value, profile.platform_id,
                ) if profile.entity_type == "creator" else None
                result = _lead_result(
                    profile, ranked, package.confidence, request,
                    recommendations.get(entity_key), match.reasoning_source,
                    match.degraded, commercial, duplicates.get(entity_key, []),
                )
                budget_status = _budget_status(result, request)
                if budget_status == "outside":
                    budget_excluded += 1
                    continue
                if budget_status == "unavailable":
                    budget_unavailable += 1
                results.append(result)
            if budget_excluded:
                extra_warnings.append(
                    f"Excluded {budget_excluded} creator {'result' if budget_excluded == 1 else 'results'} "
                    f"outside the requested {request.currency} budget range."
                )
            if budget_unavailable:
                extra_warnings.append(
                    f"Retained {budget_unavailable} creator {'result' if budget_unavailable == 1 else 'results'} "
                    "because factual pricing was unavailable; no rate was fabricated."
                )
            results.sort(key=lambda item: (-item.priority.score, -item.recommendation_score, item.entity_key))
            results = results[:request.result_limit]
            completed_at = datetime.now(timezone.utc)
            stored_results = [item.model_dump(mode="json") for item in results]
            warnings = list(dict.fromkeys([*package.warnings, *match.warnings, *extra_warnings]))
            await self.repository.update_job(job_id, {
                "status": ResearchJobStatus.COMPLETED.value, "progress": 100,
                "result_count": len(results), "confidence": round(package.confidence * 100, 2),
                "reasoning_source": match.reasoning_source, "degraded": match.degraded,
                "results": stored_results, "warnings": warnings,
                "missing_information": package.missing_information,
                "source_summary": [item.model_dump(mode="json") for item in package.source_summary],
                "completed_at": completed_at,
            })
            await self.repository.audit_event(
                actor_id, "admin_research_completed", "admin_research_job", job_id,
                ["status", "results", "reasoning_source"],
            )
            operational_metrics.increment("admin_research_jobs_completed")
        except Exception as error:
            logger.error(
                "Admin research job failed failure_class=%s", type(error).__name__,
                extra={"event": "admin_research.failed", "error_category": "dependency_unavailable"},
            )
            await self.repository.update_job(job_id, {
                "status": ResearchJobStatus.FAILED.value, "progress": 100,
                "error_code": "research_failed", "completed_at": datetime.now(timezone.utc),
                "warnings": ["Research could not be completed. Retry when factual providers are available."],
            })
            await self.repository.audit_event(
                actor_id, "admin_research_failed", "admin_research_job", job_id, ["status"],
            )
            operational_metrics.increment("admin_research_jobs_failed")

    async def get_job(self, job_id: str) -> ResearchJobDetail:
        document = await self.repository.get_job(job_id)
        if not document:
            raise HTTPException(status_code=404, detail="Research job not found")
        return _job_detail(document)

    async def history(self, **filters) -> ResearchHistoryPage:
        rows, total = await self.repository.list_jobs(**filters)
        return ResearchHistoryPage(
            items=[_job_summary(item) for item in rows], total=total,
            page=filters["page"], page_size=filters["page_size"],
        )

    async def rerun(self, job_id: str, user: dict) -> tuple[ResearchJobSummary, AdminResearchRequest]:
        original = await self.repository.get_job(job_id)
        if not original:
            raise HTTPException(status_code=404, detail="Research job not found")
        request = AdminResearchRequest.model_validate(original["criteria"])
        return await self.create_job(request, user), request

    async def save_lead(self, payload: SaveLeadRequest, user: dict) -> SavedLead:
        job = await self.repository.get_job(payload.research_id)
        if not job or job.get("status") != ResearchJobStatus.COMPLETED.value:
            raise HTTPException(status_code=404, detail="Completed research session not found")
        result = next(
            (item for item in job.get("results", []) if item.get("entity_key") == payload.entity_key), None,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Research result not found")
        document = await self.repository.save_lead(job, result, str(user.get("_id", "unknown")))
        operational_metrics.increment("admin_leads_saved")
        return _saved_lead(document)

    async def leads(self, **filters) -> SavedLeadPage:
        rows, total = await self.repository.list_leads(**filters)
        return SavedLeadPage(
            items=[_saved_lead(item) for item in rows], total=total,
            page=filters["page"], page_size=filters["page_size"],
        )

    async def get_lead(self, lead_id: str) -> SavedLead:
        document = await self.repository.get_lead(lead_id)
        if not document:
            raise HTTPException(status_code=404, detail="Saved lead not found")
        return _saved_lead(document)

    async def update_lead(self, lead_id: str, payload: LeadUpdateRequest, user: dict) -> SavedLead:
        document = await self.repository.update_lead_status(
            lead_id, payload.status, str(user.get("_id", "unknown")),
        )
        if not document:
            raise HTTPException(status_code=404, detail="Saved lead not found")
        return _saved_lead(document)

    async def add_note(self, lead_id: str, payload: LeadNoteRequest, user: dict) -> SavedLead:
        document = await self.repository.add_note(
            lead_id, payload.note, str(user.get("_id", "unknown")),
        )
        if not document:
            raise HTTPException(status_code=404, detail="Saved lead not found")
        return _saved_lead(document)

    async def archive(self, lead_id: str, user: dict) -> SavedLead:
        document = await self.repository.archive_lead(lead_id, str(user.get("_id", "unknown")))
        if not document:
            raise HTTPException(status_code=404, detail="Saved lead not found")
        return _saved_lead(document)

    async def audit(self, lead_id: str, limit: int) -> list[AuditEvent]:
        if not await self.repository.get_lead(lead_id):
            raise HTTPException(status_code=404, detail="Saved lead not found")
        return [AuditEvent(
            action=item.get("action", "unknown"),
            changed_fields=list(item.get("changed_fields", []))[:10],
            created_at=item["created_at"],
        ) for item in await self.repository.lead_audit(lead_id, limit)]

    async def analytics(self) -> LeadAnalytics:
        return LeadAnalytics.model_validate(await self.repository.analytics())

    async def ai_activity(self, page: int, page_size: int) -> AIActivityPage:
        items, total = await self.repository.ai_activity(page, page_size)
        return AIActivityPage(items=items, total=total, page=page, page_size=page_size)


def _lead_result(
    profile: NormalizedProfile, ranked, package_confidence: float,
    request: AdminResearchRequest, recommendation, reasoning_source: str,
    degraded: bool, commercial: dict | None, duplicates: list[str],
) -> LeadIntelligenceResult:
    del package_confidence
    entity_key = f"{profile.platform.value}:{profile.platform_id}"
    recommendation_score = round(ranked.score if ranked else profile.source_confidence * 100, 2)
    components = ranked.components if ranked else {}
    priority = _priority(profile, recommendation_score, commercial)
    pricing = None
    if profile.entity_type == "creator":
        analysis = analyze_pricing(
            profile, CreatorInsightInput(profile_reference=entity_key), request.currency,
        )
        pricing = PricingSummary(
            estimated_rate=analysis.estimated_rate, selected_rate=analysis.selected_rate,
            currency=analysis.currency, rate_type=analysis.rate_type,
            confidence=analysis.price_confidence, source=analysis.pricing_source,
            warnings=analysis.pricing_notes[:10],
        )
    commercial_summary = CommercialSummary(
        available=bool(commercial), currency=commercial.get("currency") if commercial else None,
        known_rate=commercial.get("current_known_rate") if commercial else None,
        negotiated_rate=commercial.get("current_negotiated_rate") if commercial else None,
        verification_status=commercial.get("rate_verification_status") if commercial else None,
    )
    assistance = _assistance(profile, request, recommendation_score, recommendation, reasoning_source, degraded, pricing)
    strengths = list(recommendation.strengths) if recommendation else _strengths(components)
    weaknesses = list(recommendation.weaknesses) if recommendation else _weaknesses(profile, components)
    why = list(recommendation.why_recommended) if recommendation else [
        f"Deterministic relevance is {recommendation_score:.1f}/100 using available normalized facts.",
        f"Source confidence is {profile.source_confidence * 100:.1f}%.",
    ]
    social_profiles = list(dict.fromkeys(filter(None, [profile.profile_url, *profile.linked_social_urls])))
    return LeadIntelligenceResult(
        entity_key=entity_key, entity_type=profile.entity_type, platform=profile.platform,
        platform_id=profile.platform_id, username=profile.username, display_name=profile.display_name,
        profile_url=profile.profile_url, biography=profile.biography, website=profile.website,
        public_social_profiles=social_profiles, available_platforms=_platforms(profile, social_profiles),
        categories=profile.categories, keywords=profile.keywords, location=profile.location,
        language=profile.language, follower_count=profile.follower_count,
        content_count=profile.content_count, average_views=profile.average_views,
        engagement_rate=profile.engagement_rate, audience_quality=None,
        marketing_signals=_marketing_signals(profile),
        estimated_collaboration_activity=(
            "Authorized commercial history is available for review."
            if commercial else None
        ),
        verification_status=(
            "verified" if profile.verified is True else
            "not_verified" if profile.verified is False else "unavailable"
        ),
        # Provider profile publication dates are not assumed to be recent content activity.
        last_observed_activity=None, collected_at=profile.collected_at,
        discovery_source=profile.source, confidence=round(profile.source_confidence * 100, 2),
        recommendation_score=recommendation_score, strengths=strengths[:8], weaknesses=weaknesses[:8],
        why_recommended=why[:8], priority=priority, assistance=assistance,
        pricing=pricing, commercial_history=commercial_summary,
        possible_duplicates=duplicates[:10], warnings=list(dict.fromkeys(profile.warnings))[:30],
    )


def _budget_status(result: LeadIntelligenceResult, request: AdminResearchRequest) -> str:
    if result.entity_type != "creator":
        return "not_applicable"
    if request.minimum_budget is None and request.maximum_budget is None:
        return "not_requested"
    rate = result.pricing.selected_rate if result.pricing else None
    if rate is None:
        return "unavailable"
    if request.minimum_budget is not None and rate < request.minimum_budget:
        return "outside"
    if request.maximum_budget is not None and rate > request.maximum_budget:
        return "outside"
    return "inside"


def _priority(profile: NormalizedProfile, commercial_fit: float, commercial: dict | None) -> PriorityScore:
    engagement = None if profile.engagement_rate is None else min(100.0, profile.engagement_rate / 5 * 100)
    platform_presence = min(100.0, 50.0 + len(profile.linked_social_urls) * 25.0)
    confidence = profile.source_confidence * 100
    commercial_score = min(100.0, commercial_fit + (5 if commercial else 0))
    values = {
        "activity": None,
        "engagement": engagement,
        "platform_presence": platform_presence,
        "commercial_fit": commercial_score,
        "source_confidence": confidence,
    }
    weights = {
        "activity": 0.15, "engagement": 0.20, "platform_presence": 0.15,
        "commercial_fit": 0.30, "source_confidence": 0.20,
    }
    available_weight = sum(weights[key] for key, value in values.items() if value is not None)
    score = sum((values[key] or 0) * weights[key] for key in values if values[key] is not None) / available_weight
    priority = LeadPriority.HIGH if score >= 75 else LeadPriority.MEDIUM if score >= 50 else LeadPriority.LOW
    explanation = [
        f"Commercial-fit relevance contributes {commercial_score:.1f}/100.",
        f"Source confidence contributes {confidence:.1f}/100.",
        f"Public platform-presence evidence contributes {platform_presence:.1f}/100.",
    ]
    if engagement is not None:
        explanation.append(f"Reported engagement is {profile.engagement_rate:.2f}%.")
    else:
        explanation.append("Engagement was unavailable and was excluded, not scored as zero.")
    explanation.append("Recent collaboration activity was unavailable and was excluded from scoring.")
    return PriorityScore(
        score=round(score, 2), priority=priority, components={
            key: None if value is None else round(value, 2) for key, value in values.items()
        }, explanation=explanation,
    )


def _assistance(profile, request, score, recommendation, reasoning_source, degraded, pricing):
    name = profile.display_name or profile.username or "this lead"
    objective = request.campaign_objective or "a measurable pilot campaign"
    category = profile.categories[0] if profile.categories else None
    if recommendation:
        return GroundedAssistance(
            why_contact=recommendation.recommendation_summary,
            campaign_fit=recommendation.campaign_fit,
            outreach_angle=recommendation.outreach.first_contact_angle,
            conversation_starter=recommendation.outreach.call_to_action,
            negotiation_guidance=_negotiation(pricing),
            reasoning_source=reasoning_source, degraded=degraded,
        )
    category_text = f" its public {category} positioning" if category else " the public profile"
    return GroundedAssistance(
        why_contact=f"{name} scored {score:.1f}/100 from available factual relevance and confidence signals.",
        campaign_fit=f"Review whether{category_text} aligns with {objective}; no campaign outcome is inferred.",
        outreach_angle=f"Reference{category_text} and ask whether {name} is open to reviewing a clearly scoped brief.",
        conversation_starter=f"Would your team be open to a short conversation about {objective} and measurable collaboration criteria?",
        negotiation_guidance="Confirm decision authority, deliverables, usage rights, timeline, and budget directly before treating any terms as agreed.",
        reasoning_source="deterministic_grounded", degraded=True,
    )


def _negotiation(pricing: PricingSummary | None) -> str:
    if pricing and pricing.selected_rate is not None:
        return (
            f"The {pricing.currency} {pricing.selected_rate:,.2f} figure is an estimate, not a quote. "
            "Confirm deliverables, usage rights, exclusivity, timing, and the creator's current rate directly."
        )
    return "Request the creator's current rate and confirm deliverables, rights, exclusivity, and timing before negotiating."


def _strengths(components) -> list[str]:
    values = components.model_dump() if hasattr(components, "model_dump") else dict(components or {})
    labels = {
        "category_relevance": "Category signals align with the search criteria.",
        "keyword_relevance": "Public keyword signals align with the search criteria.",
        "location_match": "The available location matches the requested geography.",
        "language_match": "The available language matches the request.",
        "source_confidence": "The factual source confidence is strong.",
    }
    return [labels[key] for key, value in values.items() if key in labels and value is not None and value >= 75][:8] or [
        "The profile contains enough normalized facts for deterministic comparison."
    ]


def _weaknesses(profile, components) -> list[str]:
    values = components.model_dump() if hasattr(components, "model_dump") else dict(components or {})
    output = [
        f"The {key.replace('_', ' ')} signal is weak."
        for key, value in values.items() if value is not None and value < 50
    ]
    if profile.engagement_rate is None:
        output.append("Engagement is unavailable from the factual source.")
    if profile.audience_demographics is None:
        output.append("Audience demographics are unavailable from the factual source.")
    return output[:8] or ["Campaign-specific terms and outcomes require direct validation."]


def _marketing_signals(profile) -> list[str]:
    signals = []
    if profile.categories:
        signals.append(f"Public categories: {', '.join(profile.categories[:4])}")
    if profile.follower_count is not None:
        signals.append(f"Reported followers: {profile.follower_count:,}")
    if profile.engagement_rate is not None:
        signals.append(f"Reported engagement: {profile.engagement_rate:.2f}%")
    if profile.average_views is not None:
        signals.append(f"Reported average views: {profile.average_views:,}")
    if profile.content_count is not None:
        signals.append(f"Reported content count: {profile.content_count:,}")
    return signals


def _platforms(profile, urls: list[str]) -> list[str]:
    result = [profile.platform.value]
    hosts = {
        "instagram.com": "instagram", "youtube.com": "youtube", "youtu.be": "youtube",
        "snapchat.com": "snapchat", "twitch.tv": "twitch", "x.com": "x", "twitter.com": "x",
    }
    for value in urls:
        try:
            host = (urlsplit(value).hostname or "").casefold().removeprefix("www.")
        except ValueError:
            continue
        for suffix, platform in hosts.items():
            if host == suffix or host.endswith(f".{suffix}"):
                result.append(platform)
    return list(dict.fromkeys(result))


def _duplicate_map(suggestions) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for item in suggestions:
        if item.confidence <= 0:
            continue
        output.setdefault(item.left_platform_id, []).append(item.right_platform_id)
        output.setdefault(item.right_platform_id, []).append(item.left_platform_id)
    return {key: list(dict.fromkeys(values)) for key, values in output.items()}


def _job_summary(document: dict) -> ResearchJobSummary:
    return ResearchJobSummary(
        id=str(document["_id"]), research_name=document.get("research_name"),
        entity_type=document.get("entity_type", "both"), platforms=document.get("platforms", []),
        query_summary=document.get("query_summary", ""), status=document.get("status", "queued"),
        progress=int(document.get("progress", 0)), result_count=int(document.get("result_count", 0)),
        confidence=float(document.get("confidence", 0)), reasoning_source=document.get("reasoning_source"),
        degraded=bool(document.get("degraded", False)), error_code=document.get("error_code"),
        created_at=document["created_at"], started_at=document.get("started_at"),
        completed_at=document.get("completed_at"),
    )


def _job_detail(document: dict) -> ResearchJobDetail:
    summary = _job_summary(document)
    return ResearchJobDetail(
        **summary.model_dump(), criteria=document.get("criteria", {}),
        results=[LeadIntelligenceResult.model_validate(item) for item in document.get("results", [])],
        warnings=list(document.get("warnings", [])),
        missing_information=list(document.get("missing_information", [])),
        source_summary=list(document.get("source_summary", [])),
    )


def _saved_lead(document: dict) -> SavedLead:
    return SavedLead(
        id=str(document["_id"]), research_id=document["research_id"],
        fingerprint=document["fingerprint"], status=document.get("status", "new"),
        archived=bool(document.get("archived", False)),
        result=LeadIntelligenceResult.model_validate(document["result"]),
        notes=document.get("notes", []), created_at=document["created_at"],
        updated_at=document["updated_at"],
    )
