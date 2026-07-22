import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import httpx
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria
from commercial_intelligence.models import (
    CampaignPerformanceCreate, CommercialProfileCreate, NegotiationCreate,
    RateHistoryCreate,
)
from commercial_intelligence.service import CommercialService
from creator_intelligence.engine import CreatorIntelligenceEngine
from creator_intelligence.models import CreatorIntelligenceRequest
from research_agent.agent import ResearchAgent


def run(coro):
    return asyncio.run(coro)


def now():
    return datetime.now(timezone.utc)


def fake_user(role="brand"):
    return {"_id": ObjectId(), "role": role, "email": f"{role}@example.com"}


def profile_payload(platform_id="creator-1", currency="USD", rate=None, verified="unverified"):
    return CommercialProfileCreate(
        platform="instagram", platform_id=platform_id, username=platform_id,
        currency=currency, current_known_rate=rate, rate_verification_status=verified,
    )


def rate_payload(amount=300, currency="USD", verified="unverified", effective_at=None):
    return RateHistoryCreate(
        rate_type="known", amount=amount, currency=currency, source="signed_rate_card",
        verification_status=verified, effective_at=effective_at or now(),
    )


async def database_and_service():
    mongo = AsyncMongoMockClient()
    database = mongo["commercial_intelligence"]
    return mongo, database, CommercialService(database)


async def owned_campaign(database, user):
    brand = {"_id": ObjectId(), "user_id": str(user["_id"]), "verification_status": "verified"}
    await database.brands.insert_one(brand)
    campaign = {"_id": ObjectId(), "brand_id": str(brand["_id"]), "title": "Test"}
    await database.campaigns.insert_one(campaign)
    return str(campaign["_id"])


def performance_payload(profile_id, campaign_id, **updates):
    values = {
        "campaign_id": campaign_id, "commercial_profile_id": profile_id,
        "objective": "Brand Awareness", "agreed_cost": 500, "currency": "USD",
        "deliverable_type": "video", "deliverables_committed": 2, "deliverables_completed": 2,
        "observed_reach": 10000, "observed_likes": 400, "observed_comments": 100,
        "evidence_status": "verified", "measurement_source": "platform_export",
        "measurement_period_start": now() - timedelta(days=7), "measurement_period_end": now(),
        "estimated_spend": 450, "estimated_reach": 9000, "estimated_engagements": 450,
        "estimated_cpe": 1, "estimated_cpm": 50, "creator_quality_score_at_selection": 82,
    }
    values.update(updates)
    return CampaignPerformanceCreate(**values)


async def research_request(*, use_history, creator_inputs=None):
    package = (await ResearchAgent().research(DiscoveryCriteria(
        entity_type="creator", platforms=["instagram"], niche="fitness", result_limit=5,
    ))).package
    return CreatorIntelligenceRequest(
        research_package=package, campaign_budget=1000, number_of_creators=1,
        campaign_objective="Brand Awareness", use_commercial_history=use_history,
        creator_inputs=creator_inputs or [],
    )


def test_authorized_profile_creation_and_safe_audit_metadata():
    async def scenario():
        mongo, database, service = await database_and_service()
        user = fake_user()
        created = await service.create_profile(user, profile_payload(rate=400, verified="verified"))
        assert created.current_known_rate == 400
        assert not hasattr(created, "tenant_id") and not hasattr(created, "created_by")
        audit = await database.activity_logs.find_one({"entity_id": created.id})
        assert audit["meta"].keys() == {"changed_fields"}
        assert "pricing_notes" in audit["meta"]["changed_fields"]
        mongo.close()
    run(scenario())


def test_tenant_isolation_hides_another_brand_profile():
    async def scenario():
        mongo, _, service = await database_and_service()
        owner, other = fake_user(), fake_user()
        created = await service.create_profile(owner, profile_payload())
        with pytest.raises(Exception) as exc:
            await service.get_profile(other, created.id)
        assert getattr(exc.value, "status_code", None) == 404
        assert await service.list_profiles(other, 50, None) == []
        mongo.close()
    run(scenario())


def test_invalid_rate_and_currency_are_rejected():
    with pytest.raises(ValueError):
        rate_payload(amount=-1)
    with pytest.raises(ValueError):
        profile_payload(currency="usd")


def test_verified_rate_is_not_overwritten_and_history_is_append_only():
    async def scenario():
        mongo, _, service = await database_and_service()
        user = fake_user()
        profile = await service.create_profile(user, profile_payload(rate=500, verified="verified"))
        await service.append_rate(user, profile.id, rate_payload(amount=250, verified="unverified"))
        fresh = await service.get_profile(user, profile.id)
        history = await service.list_rates(user, profile.id, 100)
        assert fresh.current_known_rate == 500
        assert len(history) == 2
        assert {item.amount for item in history} == {250, 500}
        mongo.close()
    run(scenario())


def test_rate_currency_must_match_profile():
    async def scenario():
        mongo, _, service = await database_and_service()
        user = fake_user()
        profile = await service.create_profile(user, profile_payload())
        with pytest.raises(Exception) as exc:
            await service.append_rate(user, profile.id, rate_payload(currency="EUR"))
        assert getattr(exc.value, "status_code", None) == 409
        mongo.close()
    run(scenario())


def test_negotiation_validation_keeps_quote_and_agreement_separate():
    with pytest.raises(ValueError):
        NegotiationCreate(
            currency="USD", status="agreed", initially_quoted_amount=500, occurred_at=now(),
        )
    valid = NegotiationCreate(
        currency="USD", status="agreed", initially_quoted_amount=500,
        counter_offer_amount=400, agreed_amount=425, occurred_at=now(),
    )
    assert valid.initially_quoted_amount == 500 and valid.agreed_amount == 425


def test_campaign_performance_validation_and_missing_metrics_remain_null():
    async def scenario():
        mongo, database, service = await database_and_service()
        user = fake_user()
        profile = await service.create_profile(user, profile_payload())
        campaign_id = await owned_campaign(database, user)
        sparse = performance_payload(
            profile.id, campaign_id, observed_reach=None, observed_likes=None,
            observed_comments=None, observed_views=None,
        )
        record = await service.create_performance(user, sparse)
        assert record.observed_reach is None and record.observed_likes is None
        with pytest.raises(ValueError):
            performance_payload(
                profile.id, campaign_id,
                measurement_period_start=now(), measurement_period_end=now() - timedelta(days=1),
            )
        mongo.close()
    run(scenario())


def test_verified_performance_correction_requires_reason_and_retains_version():
    async def scenario():
        mongo, database, service = await database_and_service()
        user = fake_user()
        profile = await service.create_profile(user, profile_payload())
        campaign_id = await owned_campaign(database, user)
        record = await service.create_performance(user, performance_payload(profile.id, campaign_id))
        from commercial_intelligence.models import CampaignPerformancePatch
        with pytest.raises(Exception) as exc:
            await service.patch_performance(user, record.id, CampaignPerformancePatch(observed_reach=11000))
        assert getattr(exc.value, "status_code", None) == 409
        updated = await service.patch_performance(
            user, record.id,
            CampaignPerformancePatch(observed_reach=11000, correction_reason="Corrected verified export"),
        )
        assert updated.observed_reach == 11000
        assert await database.commercial_record_versions.count_documents({"record_id": record.id}) == 1
        mongo.close()
    run(scenario())


def test_estimated_vs_actual_comparison_is_deterministic_and_noncausal():
    async def scenario():
        mongo, database, service = await database_and_service()
        user = fake_user()
        profile = await service.create_profile(user, profile_payload())
        campaign_id = await owned_campaign(database, user)
        record = await service.create_performance(user, performance_payload(profile.id, campaign_id))
        comparison = await service.comparison(user, record.id)
        assert comparison.spend.estimate == 450 and comparison.spend.observed == 500
        assert comparison.reach.estimate == 9000 and comparison.reach.observed == 10000
        assert comparison.engagements.observed == 500
        assert comparison.cpe.observed == 1
        assert "no causal attribution" in comparison.methodology.casefold()
        mongo.close()
    run(scenario())


def test_analytics_reports_sample_sizes_and_rejects_cross_currency_totals():
    async def scenario():
        mongo, _, service = await database_and_service()
        user = fake_user()
        first = await service.create_profile(user, profile_payload("one", "USD", 300))
        second = await service.create_profile(user, profile_payload("two", "EUR", 250))
        with pytest.raises(Exception) as exc:
            await service.analytics(user, now() - timedelta(days=30), now(), 100, None)
        assert getattr(exc.value, "status_code", None) == 409
        summary = await service.analytics(user, now() - timedelta(days=30), now(), 100, "USD")
        assert summary.sample_sizes["rates"] == 1
        assert summary.currency == "USD"
        assert summary.observed_cpe is None
        assert first.id != second.id
        mongo.close()
    run(scenario())


def test_analytics_date_range_is_bounded():
    async def scenario():
        mongo, _, service = await database_and_service()
        with pytest.raises(Exception) as exc:
            await service.analytics(fake_user(), now() - timedelta(days=367), now(), 100, "USD")
        assert getattr(exc.value, "status_code", None) == 422
        mongo.close()
    run(scenario())


def test_commercial_history_disabled_does_not_read_or_change_request():
    async def scenario():
        mongo, _, service = await database_and_service()
        request = await research_request(use_history=False)
        effective, warnings = await service.apply_history(fake_user(), request)
        assert effective == request and warnings == []
        mongo.close()
    run(scenario())


def test_verified_history_precedes_verified_request_without_writing():
    async def scenario():
        mongo, database, service = await database_and_service()
        user = fake_user()
        request = await research_request(use_history=True)
        normalized = request.research_package.normalized_entities[0]
        reference = f"{normalized.platform.value}:{normalized.platform_id}"
        await service.create_profile(user, CommercialProfileCreate(
            platform=normalized.platform, platform_id=normalized.platform_id,
            username=normalized.username, currency="USD", current_known_rate=325,
            rate_verification_status="verified",
        ))
        request_data = request.model_dump()
        request_data["creator_inputs"] = [{
            "profile_reference": reference,
            "pricing": {"known_rate": 500, "known_rate_verified": True},
        }]
        request = CreatorIntelligenceRequest.model_validate(request_data)
        before = await database.creator_rate_history.count_documents({})
        effective, warnings = await service.apply_history(user, request)
        result = CreatorIntelligenceEngine().recommend(effective)
        pricing = next(item for item in result.pricing_analysis if item.profile_reference == reference)
        assert pricing.selected_rate == 325
        assert pricing.pricing_source.startswith("commercial_history:")
        assert warnings
        assert await database.creator_rate_history.count_documents({}) == before
        mongo.close()
    run(scenario())


def test_stale_history_reduces_confidence_and_unverified_cannot_override_verified_request():
    async def scenario():
        mongo, _, service = await database_and_service()
        user = fake_user()
        request = await research_request(use_history=True)
        normalized = request.research_package.normalized_entities[0]
        reference = f"{normalized.platform.value}:{normalized.platform_id}"
        profile = await service.create_profile(user, CommercialProfileCreate(
            platform=normalized.platform, platform_id=normalized.platform_id,
            username=normalized.username, currency="USD",
        ))
        await service.append_rate(
            user, profile.id,
            rate_payload(amount=275, verified="unverified", effective_at=now() - timedelta(days=220)),
        )
        protected = CreatorIntelligenceRequest.model_validate({
            **request.model_dump(),
            "creator_inputs": [{
                "profile_reference": reference,
                "pricing": {"known_rate": 450, "known_rate_verified": True},
            }],
        })
        effective, warnings = await service.apply_history(user, protected)
        assert effective.creator_inputs[0].pricing.known_rate == 450
        assert warnings == []

        unprotected = request
        stale_effective, stale_warnings = await service.apply_history(user, unprotected)
        pricing = stale_effective.creator_inputs[0].pricing
        assert pricing.known_rate == 275 and pricing.price_confidence < 0.5
        assert "stale" in pricing.pricing_source
        assert stale_warnings
        mongo.close()
    run(scenario())


async def api_client(monkeypatch, role="brand"):
    mongo = AsyncMongoMockClient()
    database = mongo["commercial_api"]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    security._RL_BUCKETS.clear()
    user = {"email": f"{role}-{ObjectId()}@example.com", "name": role, "role": role,
            "status": "active", "email_verified": True, "created_at": now(), "updated_at": now()}
    inserted = await database.users.insert_one(user)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
    client.cookies.set("access_token", server.create_access_token(str(inserted.inserted_id), user["email"], role))
    return mongo, database, client


def test_commercial_api_authorization_and_cross_tenant_isolation(monkeypatch):
    async def scenario():
        owner_mongo, _, owner = await api_client(monkeypatch, "brand")
        created = await owner.post("/api/creator-commercial/profiles", json={
            "platform": "instagram", "platform_id": "api-owner", "currency": "USD",
        })
        assert created.status_code == 201, created.text
        profile_id = created.json()["id"]
        await owner.aclose()

        # Reuse the same database but authenticate a second brand.
        database = server.db
        other_user = {"email": "other-brand@example.com", "name": "other", "role": "brand",
                      "status": "active", "email_verified": True, "created_at": now(), "updated_at": now()}
        inserted = await database.users.insert_one(other_user)
        other = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
        other.cookies.set("access_token", server.create_access_token(str(inserted.inserted_id), other_user["email"], "brand"))
        try:
            hidden = await other.get(f"/api/creator-commercial/profiles/{profile_id}")
            assert hidden.status_code == 404
            listing = await other.get("/api/creator-commercial/profiles")
            assert listing.status_code == 200 and listing.json() == []
        finally:
            await other.aclose()
            owner_mongo.close()
    run(scenario())


def test_commercial_api_rejects_creator_role_and_unsafe_limit(monkeypatch):
    async def scenario():
        mongo, _, client = await api_client(monkeypatch, "creator")
        try:
            forbidden = await client.post("/api/creator-commercial/profiles", json={
                "platform": "instagram", "platform_id": "no-access", "currency": "USD",
            })
            assert forbidden.status_code == 403
            invalid_limit = await client.get("/api/creator-commercial/profiles?limit=1000")
            assert invalid_limit.status_code == 422
        finally:
            await client.aclose()
            mongo.close()
    run(scenario())


def test_openapi_has_no_duplicate_routes_or_operation_ids():
    schema = server.app.openapi()
    operations = []
    pairs = []
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method.casefold() not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            pairs.append((path, method.casefold()))
            operations.append(operation["operationId"])
    assert len(pairs) == len(set(pairs))
    assert len(operations) == len(set(operations))
    assert "/api/creator-commercial/profiles" in schema["paths"]
    assert "/api/campaign-performance/{record_id}/comparison" in schema["paths"]
