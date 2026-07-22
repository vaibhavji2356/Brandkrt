import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria
from creator_intelligence.engine import CreatorIntelligenceEngine
from creator_intelligence.models import CreatorIntelligenceRequest
from research_agent.agent import ResearchAgent


def run(coro):
    return asyncio.run(coro)


def research_package():
    return run(ResearchAgent().research(DiscoveryCriteria(
        entity_type="creator", platforms=["instagram"], niche="fitness", result_limit=5,
    ))).package


def payload(*, creator_inputs=None, budget=1000, count=2, minimum_reach=None):
    return CreatorIntelligenceRequest(
        research_package=research_package(), campaign_budget=budget,
        number_of_creators=count, minimum_reach=minimum_reach,
        campaign_objective="Brand Awareness", currency="USD",
        creator_inputs=creator_inputs or [],
    )


def refs(package):
    return [f"{profile.platform.value}:{profile.platform_id}" for profile in package.normalized_entities]


def test_pricing_precedence_preserves_verified_rate_over_manual_override():
    pkg = research_package()
    reference = refs(pkg)[0]
    request = CreatorIntelligenceRequest(
        research_package=pkg, campaign_budget=1000, number_of_creators=1,
        campaign_objective="Product Review", creator_inputs=[{
            "profile_reference": reference,
            "pricing": {
                "known_rate": 425, "known_rate_verified": True,
                "manual_rate_override": 200, "pricing_source": "signed_rate_card",
            },
        }],
    )
    result = CreatorIntelligenceEngine().recommend(request)
    pricing = next(item for item in result.pricing_analysis if item.profile_reference == reference)
    assert pricing.selected_rate == 425
    assert pricing.rate_type == "verified_known"
    assert pricing.verified_rate_preserved is True
    assert pricing.manual_override_applied is False
    assert any("ignored" in note.casefold() for note in pricing.pricing_notes)


def test_manual_override_replaces_only_an_estimate():
    pkg = research_package()
    reference = refs(pkg)[0]
    result = CreatorIntelligenceEngine().recommend(CreatorIntelligenceRequest(
        research_package=pkg, campaign_budget=1000, number_of_creators=1,
        campaign_objective="Sales", creator_inputs=[{
            "profile_reference": reference,
            "pricing": {"estimated_rate": 300, "manual_rate_override": 250},
        }],
    ))
    pricing = next(item for item in result.pricing_analysis if item.profile_reference == reference)
    assert pricing.selected_rate == 250 and pricing.manual_override_applied is True
    assert pricing.estimated_rate == 300


def test_missing_metrics_are_null_and_lower_confidence_not_zero_quality():
    pkg = research_package()
    stripped = [profile.model_copy(update={
        "average_views": None, "average_likes": None, "average_comments": None,
        "engagement_rate": None, "verified": None, "follower_count": None,
    }) for profile in pkg.normalized_entities]
    package = pkg.model_copy(update={"normalized_entities": stripped})
    result = CreatorIntelligenceEngine().recommend(CreatorIntelligenceRequest(
        research_package=package, campaign_budget=1000, number_of_creators=1,
        campaign_objective="App Install",
    ))
    recommendation = result.recommendations[0]
    assert recommendation.metrics.average_views is None
    assert recommendation.metrics.roi_score is None
    assert recommendation.metrics.creator_quality_score is None
    assert recommendation.metrics.confidence < pkg.confidence
    assert recommendation.pricing.selected_rate is None


def test_roi_uses_observed_metrics_and_is_labeled_as_estimate():
    pkg = research_package()
    reference = refs(pkg)[0]
    result = CreatorIntelligenceEngine().recommend(CreatorIntelligenceRequest(
        research_package=pkg, campaign_budget=1000, number_of_creators=1,
        campaign_objective="Gaming Launch", creator_inputs=[{
            "profile_reference": reference,
            "average_views": 10000, "average_likes": 450, "average_comments": 50,
            "pricing": {"known_rate": 500, "known_rate_verified": True},
        }],
    ))
    creator = next(item for item in result.recommendations if item.profile_reference == reference)
    assert creator.roi.expected_reach == 10000
    assert creator.roi.expected_engagements == 500
    assert creator.roi.cost_per_engagement == 1
    assert creator.roi.cpm_reach == 50
    assert any("not a revenue" in warning.casefold() for warning in creator.roi.warnings)


def test_budget_optimizer_selects_affordable_portfolio_deterministically():
    pkg = research_package()
    first, second = refs(pkg)
    request = CreatorIntelligenceRequest(
        research_package=pkg, campaign_budget=500, number_of_creators=2,
        campaign_objective="Brand Awareness", creator_inputs=[
            {"profile_reference": first, "pricing": {"known_rate": 600, "known_rate_verified": True}},
            {"profile_reference": second, "pricing": {"known_rate": 400, "known_rate_verified": True}},
        ],
    )
    engine = CreatorIntelligenceEngine()
    first_result = engine.recommend(request)
    second_result = engine.recommend(request)
    assert first_result == second_result
    assert [item.profile_reference for item in first_result.recommendations if item.selected] == [second]
    assert first_result.budget_analysis.expected_spend == 400
    assert first_result.budget_analysis.remaining_budget == 100
    assert first_result.budget_analysis.selected_creator_count == 1


def test_portfolio_reports_reach_and_minimum_reach_without_fabrication():
    result = CreatorIntelligenceEngine().recommend(payload(budget=1000, count=2, minimum_reach=20000))
    assert result.budget_analysis.expected_reach == 18000
    assert result.budget_analysis.minimum_reach_met is False
    assert any("minimum reach" in warning.casefold() for warning in result.budget_analysis.warnings)


def test_response_contains_pricing_ranking_confidence_and_safe_explanation():
    result = CreatorIntelligenceEngine().recommend(payload())
    assert result.ranking and result.pricing_analysis and result.recommendations
    assert 0 <= result.confidence <= 1
    assert result.reasoning_source == "deterministic_creator_intelligence"
    serialized = result.model_dump_json().casefold()
    assert "guarantee" in serialized
    assert "revenue" in serialized


def test_request_rejects_mixed_creator_currency():
    pkg = research_package()
    try:
        CreatorIntelligenceRequest(
            research_package=pkg, campaign_budget=1000, number_of_creators=1,
            campaign_objective="Sales", currency="USD", creator_inputs=[{
                "profile_reference": refs(pkg)[0], "currency": "EUR",
            }],
        )
        assert False, "mixed currency request should fail validation"
    except ValueError as exc:
        assert "currency" in str(exc).casefold()


async def authenticated_client(monkeypatch, role="brand"):
    mongo = AsyncMongoMockClient()
    database = mongo["creator_intelligence_endpoint"]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    security._RL_BUCKETS.clear()
    now = datetime.now(timezone.utc)
    inserted = await database.users.insert_one({
        "email": f"{role}@example.com", "name": role, "role": role,
        "status": "active", "email_verified": True, "created_at": now, "updated_at": now,
    })
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
    client.cookies.set("access_token", server.create_access_token(str(inserted.inserted_id), f"{role}@example.com", role))
    return mongo, database, client


def test_protected_endpoint_returns_recommendation_without_database_writes(monkeypatch):
    request = payload()

    async def scenario():
        mongo, database, client = await authenticated_client(monkeypatch)
        before_users = await database.users.count_documents({})
        try:
            response = await client.post(
                "/api/ai/creator-intelligence/recommendations",
                json=request.model_dump(mode="json"),
            )
            assert response.status_code == 200, response.text
            assert response.json()["recommendations"]
            assert await database.users.count_documents({}) == before_users
            assert await database.list_collection_names() == ["users"]
        finally:
            await client.aclose()
            mongo.close()

    run(scenario())


def test_endpoint_rejects_unauthorized_role_and_invalid_budget(monkeypatch):
    request = payload()

    async def scenario():
        mongo, _, client = await authenticated_client(monkeypatch, role="creator")
        try:
            forbidden = await client.post(
                "/api/ai/creator-intelligence/recommendations",
                json=request.model_dump(mode="json"),
            )
            assert forbidden.status_code == 403
            invalid = request.model_dump(mode="json")
            invalid["campaign_budget"] = 0
            validation = await client.post("/api/ai/creator-intelligence/recommendations", json=invalid)
            assert validation.status_code == 422
        finally:
            await client.aclose()
            mongo.close()

    run(scenario())
