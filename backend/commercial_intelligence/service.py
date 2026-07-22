"""Ownership, integrity, attribution, analytics, and history integration rules."""

from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Any

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from creator_intelligence.models import CreatorInsightInput, CreatorIntelligenceRequest, CreatorPricingInput

from .models import (
    AnalyticsSummary, CampaignPerformanceCreate, CampaignPerformancePatch,
    CampaignPerformanceRecord, CommercialProfile, CommercialProfileCreate,
    CommercialProfilePatch, MetricComparison, NegotiationCreate, NegotiationRecord,
    PerformanceComparison, RateHistoryCreate, RateHistoryRecord, RateType,
    VerificationStatus,
)
from .repository import CommercialRepository, public_document


def tenant_scope(user: dict) -> str | None:
    return None if user.get("role") == "admin" else str(user["_id"])


def write_tenant(user: dict) -> str:
    return str(user["_id"])


def require_commercial_role(user: dict) -> None:
    if user.get("role") not in {"brand", "admin"}:
        raise HTTPException(status_code=403, detail="Forbidden")


class CommercialService:
    def __init__(self, database):
        self.db = database
        self.repository = CommercialRepository(database)

    async def create_profile(self, user: dict, payload: CommercialProfileCreate) -> CommercialProfile:
        require_commercial_role(user)
        tenant_id, actor_id = write_tenant(user), str(user["_id"])
        platform_id = payload.platform_id.strip()
        if await self.repository.find_profile_by_identity(tenant_id, payload.platform.value, platform_id):
            raise HTTPException(status_code=409, detail="Commercial profile already exists")
        now = _now()
        document = payload.model_dump(mode="python")
        document.update({
            "platform": payload.platform.value, "platform_id": platform_id,
            "rate_verification_status": payload.rate_verification_status.value,
            "created_at": now, "updated_at": now,
        })
        try:
            profile = await self.repository.create_profile(tenant_id, actor_id, document)
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Commercial profile already exists") from None
        profile_id = str(profile["_id"])
        for rate_type, amount in ((RateType.KNOWN, payload.current_known_rate), (RateType.NEGOTIATED, payload.current_negotiated_rate)):
            if amount is not None:
                await self.repository.append_rate(tenant_id, actor_id, profile_id, {
                    "rate_type": rate_type.value, "amount": amount, "currency": payload.currency,
                    "min_amount": None, "max_amount": None, "source": "commercial_profile_initial",
                    "verification_status": payload.rate_verification_status.value,
                    "effective_at": now, "notes": [], "created_at": now,
                })
        await self.repository.audit(actor_id, "creator_commercial.profile.create", "creator_commercial_profile", profile_id, list(document))
        return CommercialProfile.model_validate(public_document(profile))

    async def list_profiles(self, user: dict, limit: int, platform: str | None) -> list[CommercialProfile]:
        require_commercial_role(user)
        records = await self.repository.list_profiles(tenant_scope(user), limit, platform)
        return [CommercialProfile.model_validate(public_document(item)) for item in records]

    async def get_profile(self, user: dict, profile_id: str) -> CommercialProfile:
        profile = await self._owned_profile(user, profile_id)
        return CommercialProfile.model_validate(public_document(profile))

    async def patch_profile(self, user: dict, profile_id: str,
                            payload: CommercialProfilePatch) -> CommercialProfile:
        profile = await self._owned_profile(user, profile_id)
        changes = payload.model_dump(exclude_unset=True, exclude={"correction_reason"})
        if not changes:
            return CommercialProfile.model_validate(public_document(profile))
        changes["updated_at"] = _now()
        updated = await self.repository.patch_profile(profile, str(user["_id"]), changes)
        await self.repository.audit(str(user["_id"]), "creator_commercial.profile.update",
                                    "creator_commercial_profile", profile_id, list(changes))
        return CommercialProfile.model_validate(public_document(updated))

    async def append_rate(self, user: dict, profile_id: str,
                          payload: RateHistoryCreate) -> RateHistoryRecord:
        profile = await self._owned_profile(user, profile_id)
        if payload.currency != profile["currency"]:
            raise HTTPException(status_code=409, detail="Rate currency must match commercial profile currency")
        now = _now()
        document = payload.model_dump(mode="python")
        document.update({"rate_type": payload.rate_type.value,
                         "verification_status": payload.verification_status.value, "created_at": now})
        rate = await self.repository.append_rate(profile["tenant_id"], str(user["_id"]), profile_id, document)
        update: dict[str, Any] = {"updated_at": now}
        can_replace_current = (
            payload.verification_status != VerificationStatus.REJECTED
            and not (
                profile.get("rate_verification_status") == VerificationStatus.VERIFIED.value
                and payload.verification_status != VerificationStatus.VERIFIED
            )
        )
        if can_replace_current and payload.amount is not None and payload.rate_type in {RateType.KNOWN, RateType.NEGOTIATED}:
            update[f"current_{payload.rate_type.value}_rate"] = payload.amount
            update["rate_verification_status"] = payload.verification_status.value
        await self.repository.patch_profile(profile, str(user["_id"]), update)
        await self.repository.audit(str(user["_id"]), "creator_commercial.rate.append",
                                    "creator_rate_history", str(rate["_id"]), list(document))
        return RateHistoryRecord.model_validate(public_document(rate))

    async def list_rates(self, user: dict, profile_id: str, limit: int) -> list[RateHistoryRecord]:
        await self._owned_profile(user, profile_id)
        records = await self.repository.list_rates(tenant_scope(user), profile_id, limit)
        return [RateHistoryRecord.model_validate(public_document(item)) for item in records]

    async def append_negotiation(self, user: dict, profile_id: str,
                                 payload: NegotiationCreate) -> NegotiationRecord:
        profile = await self._owned_profile(user, profile_id)
        if payload.currency != profile["currency"]:
            raise HTTPException(status_code=409, detail="Negotiation currency must match commercial profile currency")
        if payload.campaign_id:
            await self._require_campaign_access(user, payload.campaign_id)
        now = _now()
        document = payload.model_dump(mode="python")
        document.update({"status": payload.status.value, "created_at": now})
        record = await self.repository.append_negotiation(
            profile["tenant_id"], str(user["_id"]), profile_id, document,
        )
        await self.repository.audit(str(user["_id"]), "creator_commercial.negotiation.append",
                                    "creator_negotiation", str(record["_id"]), list(document))
        return NegotiationRecord.model_validate(public_document(record))

    async def list_negotiations(self, user: dict, profile_id: str, limit: int) -> list[NegotiationRecord]:
        await self._owned_profile(user, profile_id)
        records = await self.repository.list_negotiations(tenant_scope(user), profile_id, limit)
        return [NegotiationRecord.model_validate(public_document(item)) for item in records]

    async def create_performance(self, user: dict,
                                 payload: CampaignPerformanceCreate) -> CampaignPerformanceRecord:
        profile = await self._owned_profile(user, payload.commercial_profile_id)
        await self._require_campaign_access(user, payload.campaign_id)
        if payload.currency != profile["currency"]:
            raise HTTPException(status_code=409, detail="Performance currency must match commercial profile currency")
        now = _now()
        warnings = _deliverable_warnings(payload.deliverables_committed, payload.deliverables_completed)
        document = payload.model_dump(mode="python")
        document.update({
            "objective": payload.objective.value, "evidence_status": payload.evidence_status.value,
            "platform": profile["platform"], "platform_id": profile["platform_id"],
            "username": profile.get("username"), "warnings": warnings,
            "created_at": now, "updated_at": now,
        })
        record = await self.repository.create_performance(profile["tenant_id"], str(user["_id"]), document)
        await self.repository.audit(str(user["_id"]), "campaign_performance.create",
                                    "campaign_performance", str(record["_id"]), list(document))
        return CampaignPerformanceRecord.model_validate(public_document(record))

    async def get_performance(self, user: dict, record_id: str) -> CampaignPerformanceRecord:
        record = await self._owned_performance(user, record_id)
        return CampaignPerformanceRecord.model_validate(public_document(record))

    async def list_performance(self, user: dict, limit: int) -> list[CampaignPerformanceRecord]:
        require_commercial_role(user)
        records = await self.repository.list_performance(tenant_scope(user), limit)
        return [CampaignPerformanceRecord.model_validate(public_document(item)) for item in records]

    async def patch_performance(self, user: dict, record_id: str,
                                payload: CampaignPerformancePatch) -> CampaignPerformanceRecord:
        record = await self._owned_performance(user, record_id)
        changes = payload.model_dump(exclude_unset=True, exclude={"correction_reason"}, mode="python")
        if not changes:
            return CampaignPerformanceRecord.model_validate(public_document(record))
        if record.get("evidence_status") == VerificationStatus.VERIFIED.value and not payload.correction_reason:
            raise HTTPException(status_code=409, detail="Verified performance corrections require correction_reason")
        merged_start = changes.get("measurement_period_start", record["measurement_period_start"])
        merged_end = changes.get("measurement_period_end", record["measurement_period_end"])
        if merged_start > merged_end:
            raise HTTPException(status_code=422, detail="Invalid measurement period")
        if "evidence_status" in changes and isinstance(changes["evidence_status"], VerificationStatus):
            changes["evidence_status"] = changes["evidence_status"].value
        changes["warnings"] = _deliverable_warnings(
            changes.get("deliverables_committed", record.get("deliverables_committed")),
            changes.get("deliverables_completed", record.get("deliverables_completed")),
        )
        changes["updated_at"] = _now()
        updated = await self.repository.patch_performance(
            record, str(user["_id"]), changes, payload.correction_reason,
        )
        await self.repository.audit(str(user["_id"]), "campaign_performance.correct",
                                    "campaign_performance", record_id, list(changes))
        return CampaignPerformanceRecord.model_validate(public_document(updated))

    async def comparison(self, user: dict, record_id: str) -> PerformanceComparison:
        record = await self._owned_performance(user, record_id)
        return build_performance_comparison(record)

    async def analytics(self, user: dict, start: datetime, end: datetime,
                        limit: int, currency: str | None) -> AnalyticsSummary:
        require_commercial_role(user)
        if start.tzinfo is None or end.tzinfo is None:
            raise HTTPException(status_code=422, detail="Analytics timestamps must be timezone-aware")
        if start > end or end - start > timedelta(days=366):
            raise HTTPException(status_code=422, detail="Analytics date range must be ordered and at most 366 days")
        rates, negotiations, performance = await self.repository.analytics_records(
            tenant_scope(user), start, end, limit, currency,
        )
        currencies = {
            item.get("currency") for item in [*rates, *negotiations, *performance] if item.get("currency")
        }
        if currency is None and len(currencies) > 1:
            raise HTTPException(status_code=409, detail="Select one currency for commercial aggregation")
        return build_analytics(rates, negotiations, performance, currency or next(iter(currencies), None))

    async def apply_history(self, user: dict,
                            request: CreatorIntelligenceRequest) -> tuple[CreatorIntelligenceRequest, list[str]]:
        if not request.use_commercial_history:
            return request, []
        require_commercial_role(user)
        tenant_id = write_tenant(user)
        profiles = await self.repository.list_profiles(tenant_id, 100)
        profile_by_ref = {f"{item['platform']}:{item['platform_id']}".casefold(): item for item in profiles}
        profile_ids = [str(item["_id"]) for item in profiles]
        rates_by_profile = await self.repository.latest_rates_for_profiles(tenant_id, profile_ids)
        inputs = {item.profile_reference.casefold(): item for item in request.creator_inputs}
        warnings: list[str] = []
        for normalized in request.research_package.normalized_entities:
            reference = f"{normalized.platform.value}:{normalized.platform_id}"
            commercial = profile_by_ref.get(reference.casefold())
            if not commercial:
                continue
            if commercial["currency"] != request.currency:
                warnings.append(f"Commercial history for {reference} was ignored because its currency differs from the campaign currency.")
                continue
            history = rates_by_profile.get(str(commercial["_id"]), [])
            chosen = _choose_history_rate(history)
            if not chosen or chosen.get("amount") is None:
                continue
            existing = inputs.get(reference.casefold()) or CreatorInsightInput(profile_reference=reference)
            merged_pricing, applied = _merge_history_pricing(existing.pricing, chosen)
            if not applied:
                continue
            inputs[reference.casefold()] = existing.model_copy(update={"pricing": merged_pricing, "currency": request.currency})
            warnings.append(f"Tenant-owned commercial pricing history was applied to {reference} without modifying stored records.")
        return request.model_copy(update={"creator_inputs": list(inputs.values())}), warnings

    async def _owned_profile(self, user: dict, profile_id: str) -> dict:
        require_commercial_role(user)
        try:
            profile = await self.repository.get_profile(profile_id, tenant_scope(user))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid profile id") from None
        if not profile:
            raise HTTPException(status_code=404, detail="Commercial profile not found")
        return profile

    async def _owned_performance(self, user: dict, record_id: str) -> dict:
        require_commercial_role(user)
        try:
            record = await self.repository.get_performance(record_id, tenant_scope(user))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid performance record id") from None
        if not record:
            raise HTTPException(status_code=404, detail="Performance record not found")
        return record

    async def _require_campaign_access(self, user: dict, campaign_id: str) -> None:
        try:
            from bson import ObjectId
            query_id = ObjectId(campaign_id) if ObjectId.is_valid(campaign_id) else campaign_id
        except Exception:
            query_id = campaign_id
        campaign = await self.db.campaigns.find_one({"_id": query_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if user.get("role") == "admin":
            return
        user_id = str(user["_id"])
        brand = await self.db.brands.find_one({"user_id": user_id})
        owned_ids = {user_id}
        if brand:
            owned_ids.add(str(brand["_id"]))
        if str(campaign.get("brand_id") or campaign.get("brand_user_id") or "") not in owned_ids:
            raise HTTPException(status_code=403, detail="Campaign is not owned by the authenticated brand")


def build_performance_comparison(record: dict) -> PerformanceComparison:
    verified = record.get("evidence_status") == VerificationStatus.VERIFIED.value
    observed_status = "verified" if verified else "unverified"
    observed_engagements = _sum_if_any(record, "observed_likes", "observed_comments", "observed_shares")
    observed_reach = record.get("observed_reach")
    actual_cost = record.get("agreed_cost")
    actual_cpe = round(actual_cost / observed_engagements, 4) if actual_cost is not None and observed_engagements else None
    actual_cpm = round(actual_cost / observed_reach * 1000, 4) if actual_cost is not None and observed_reach else None
    completed = record.get("deliverables_completed")
    committed = record.get("deliverables_committed")
    completion = round(completed / committed * 100, 2) if committed and completed is not None else None
    efficiency_values = []
    if actual_cpe is not None:
        efficiency_values.append(max(0.0, min(100.0, 100 - actual_cpe * 10)))
    if actual_cpm is not None:
        efficiency_values.append(max(0.0, min(100.0, 100 - actual_cpm * 2)))
    return PerformanceComparison(
        performance_record_id=str(record["_id"]), currency=record["currency"],
        spend=_comparison(record.get("estimated_spend"), actual_cost, observed_status),
        reach=_comparison(record.get("estimated_reach"), observed_reach, observed_status),
        engagements=_comparison(record.get("estimated_engagements"), observed_engagements, observed_status),
        cpe=_comparison(record.get("estimated_cpe"), actual_cpe, observed_status),
        cpm=_comparison(record.get("estimated_cpm"), actual_cpm, observed_status),
        deliverables=_comparison(committed, completed, observed_status),
        creator_quality_score_at_selection=record.get("creator_quality_score_at_selection"),
        observed_campaign_efficiency_score=round(fmean(efficiency_values), 2) if efficiency_values else None,
        methodology="Deterministic estimate-versus-observation comparison; no causal attribution is claimed.",
        warnings=list(dict.fromkeys(record.get("warnings", []) + [
            "Revenue and conversion observations are reported only when supplied; causality is not inferred.",
            "Followers are not substituted for observed reach.",
        ])),
    )


def build_analytics(rates: list[dict], negotiations: list[dict], performance: list[dict],
                    currency: str | None) -> AnalyticsSummary:
    usable_rates = [item for item in rates if item.get("amount") is not None]
    discounts = []
    quoted_total = agreed_total = 0.0
    negotiation_pairs = 0
    for item in negotiations:
        quoted, agreed = item.get("initially_quoted_amount"), item.get("agreed_amount")
        if quoted is not None and agreed is not None:
            quoted_total += quoted
            agreed_total += agreed
            negotiation_pairs += 1
            if quoted > 0:
                discounts.append((quoted - agreed) / quoted * 100)
    spend_by_creator: dict[str, float] = {}
    spend_by_platform: dict[str, float] = {}
    repeat: dict[str, int] = {}
    cpe_cost = cpe_engagements = cpm_cost = cpm_reach = 0.0
    completed = committed = 0
    deliverable_samples = 0
    variances = []
    low_evidence = missing = 0
    for item in performance:
        reference = f"{item.get('platform')}:{item.get('platform_id')}"
        cost = item.get("agreed_cost")
        if cost is not None:
            spend_by_creator[reference] = round(spend_by_creator.get(reference, 0) + cost, 2)
            platform = item.get("platform", "unknown")
            spend_by_platform[platform] = round(spend_by_platform.get(platform, 0) + cost, 2)
        repeat[reference] = repeat.get(reference, 0) + 1
        engagements = _sum_if_any(item, "observed_likes", "observed_comments", "observed_shares")
        if cost is not None and engagements:
            cpe_cost += cost
            cpe_engagements += engagements
        if cost is not None and item.get("observed_reach"):
            cpm_cost += cost
            cpm_reach += item["observed_reach"]
        if item.get("deliverables_committed") is not None and item.get("deliverables_completed") is not None:
            committed += item["deliverables_committed"]
            completed += item["deliverables_completed"]
            deliverable_samples += 1
        if item.get("estimated_reach") not in (None, 0) and item.get("observed_reach") is not None:
            variances.append((item["observed_reach"] - item["estimated_reach"]) / item["estimated_reach"] * 100)
        if item.get("evidence_status") != VerificationStatus.VERIFIED.value:
            low_evidence += 1
        if all(item.get(field) is None for field in ("observed_reach", "observed_views", "observed_likes", "observed_comments", "observed_shares")):
            missing += 1
    return AnalyticsSummary(
        currency=currency,
        sample_sizes={"rates": len(rates), "negotiations": len(negotiations), "performance": len(performance),
                      "negotiated_pairs": negotiation_pairs, "deliverable_records": deliverable_samples},
        rate_trend=[{
            "effective_at": item["effective_at"].isoformat(), "rate_type": item["rate_type"],
            "amount": item.get("amount"), "verification_status": item["verification_status"],
        } for item in usable_rates],
        average_negotiated_discount_percent=round(fmean(discounts), 2) if discounts else None,
        quoted_vs_agreed={"quoted": round(quoted_total, 2) if negotiation_pairs else None,
                          "agreed": round(agreed_total, 2) if negotiation_pairs else None,
                          "sample_size": negotiation_pairs},
        campaign_spend_by_creator=spend_by_creator, campaign_spend_by_platform=spend_by_platform,
        observed_cpe=round(cpe_cost / cpe_engagements, 4) if cpe_engagements else None,
        observed_cpm=round(cpm_cost / cpm_reach * 1000, 4) if cpm_reach else None,
        deliverable_completion_rate=round(completed / committed * 100, 2) if committed else None,
        creator_repeat_collaboration_count=repeat,
        average_reach_variance_percent=round(fmean(variances), 2) if variances else None,
        low_evidence_record_count=low_evidence, missing_performance_record_count=missing,
        evidence_notes=[
            "Aggregates include only records with the required observed denominator.",
            "Missing metrics are excluded, not treated as zero.",
            "Analytics are descriptive and do not establish creator causality.",
        ],
    )


def _choose_history_rate(records: list[dict]) -> dict | None:
    usable = [item for item in records if item.get("rate_type") in {"known", "negotiated"} and item.get("amount") is not None]
    verified = [item for item in usable if item.get("verification_status") == VerificationStatus.VERIFIED.value]
    candidates = verified or usable
    if not candidates:
        return None
    def ordering(item: dict):
        effective = item["effective_at"]
        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=timezone.utc)
        return effective.timestamp(), item.get("rate_type") == "negotiated"
    return max(candidates, key=ordering)


def _merge_history_pricing(existing: CreatorPricingInput | None, history: dict) -> tuple[CreatorPricingInput, bool]:
    base = existing or CreatorPricingInput()
    history_verified = history.get("verification_status") == VerificationStatus.VERIFIED.value
    request_verified = bool(base.known_rate_verified or base.negotiated_rate_verified)
    if not history_verified and (request_verified or base.manual_rate_override is not None):
        return base, False
    effective_at = history["effective_at"]
    if effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=timezone.utc)
    else:
        effective_at = effective_at.astimezone(timezone.utc)
    age_days = max(0, (_now() - effective_at).days)
    stale = age_days > 180
    confidence = (0.92 if history_verified else 0.62) * (0.6 if stale else 1.0)
    update = base.model_dump()
    update.update({
        "known_rate": None, "known_rate_verified": False,
        "negotiated_rate": None, "negotiated_rate_verified": False,
        "price_confidence": round(confidence, 4),
        "pricing_source": f"commercial_history:{history.get('source', 'unspecified')}:{'stale' if stale else 'current'}",
        "pricing_notes": list(dict.fromkeys([*base.pricing_notes,
            f"Commercial history effective {effective_at.date().isoformat()} ({'stale' if stale else 'current'})."])),
    })
    field = "negotiated_rate" if history["rate_type"] == "negotiated" else "known_rate"
    update[field] = history["amount"]
    update[f"{field}_verified"] = history_verified
    return CreatorPricingInput.model_validate(update), True


def _comparison(estimate: float | int | None, observed: float | int | None,
                observed_status: str) -> MetricComparison:
    variance = None
    if estimate not in (None, 0) and observed is not None:
        variance = round((observed - estimate) / estimate * 100, 2)
    return MetricComparison(
        estimate=estimate, observed=observed, variance=variance,
        estimate_status="estimate" if estimate is not None else "unavailable",
        observed_status=observed_status if observed is not None else "unavailable",
    )


def _sum_if_any(record: dict, *fields: str) -> int | None:
    values = [record.get(field) for field in fields]
    return sum(value or 0 for value in values) if any(value is not None for value in values) else None


def _deliverable_warnings(committed: int | None, completed: int | None) -> list[str]:
    if committed is not None and completed is not None and completed > committed:
        return ["Completed deliverables exceed committed deliverables; retain correction evidence."]
    return []


def _now() -> datetime:
    return datetime.now(timezone.utc)
