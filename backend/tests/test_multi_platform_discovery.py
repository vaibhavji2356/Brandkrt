import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
from mongomock_motor import AsyncMongoMockClient
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.discovery_service import MultiPlatformDiscoveryService
from brand_discovery_ai.identity import suggest_identity
from brand_discovery_ai.normalization import deduplicate_profiles, normalize_payload
from brand_discovery_ai.ranking import rank_profile
from brand_discovery_ai.source_adapters import CAPABILITY_REGISTRY, build_mock_adapters


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("platform", list(Platform))
def test_each_platform_adapter_is_deterministic_and_network_free(platform):
    async def scenario():
        adapter = build_mock_adapters()[platform]
        criteria = DiscoveryCriteria(entity_type="creator", platforms=[platform])
        first = await adapter.search_creators(criteria)
        second = await adapter.search_creators(criteria)
        assert first == second and first
        assert all(item.platform == platform and item.source == f"mock:{platform.value}" for item in first)
        assert await adapter.health_check() == {"status": "ok", "platform": platform.value, "mock": True, "network": False}
    run(scenario())


@pytest.mark.parametrize("entity_type,expected", [("creator", {"creator"}), ("brand", {"brand"}), ("both", {"creator", "brand"})])
def test_entity_type_search_modes(entity_type, expected):
    response = run(MultiPlatformDiscoveryService().preview(DiscoveryCriteria(entity_type=entity_type, platforms=["instagram"], result_limit=20)))
    assert {item.profile.entity_type for item in response.results} == expected


def test_platform_filtering():
    response = run(MultiPlatformDiscoveryService().preview(DiscoveryCriteria(platforms=["youtube", "x"], result_limit=20)))
    assert {item.profile.platform for item in response.results} == {Platform.YOUTUBE, Platform.X}


def test_unsupported_capabilities_and_missing_metrics_are_explicit():
    assert CAPABILITY_REGISTRY[Platform.SNAPCHAT].follower_metrics is False
    assert CAPABILITY_REGISTRY[Platform.SNAPCHAT].brand_discovery is False
    response = run(MultiPlatformDiscoveryService().preview(DiscoveryCriteria(entity_type="brand", platforms=["snapchat"])))
    assert response.results == []
    assert "unsupported" in response.warnings[-1].lower()
    creator = run(build_mock_adapters()[Platform.SNAPCHAT].search_creators(DiscoveryCriteria(platforms=["snapchat"])))
    assert creator[0].follower_count is None and creator[0].engagement_rate is None


def test_normalization_rejects_unsafe_urls_and_invalid_metrics():
    profile = normalize_payload(Platform.X, {
        "id": "x-1", "entity_type": "creator", "profile_url": "javascript:alert(1)",
        "website": "http://127.0.0.1/private", "follower_count": -2,
        "average_views": "many", "engagement_rate": 120, "collected_at": "bad",
    }, "mock:x")
    assert profile.profile_url is None and profile.website is None
    assert profile.follower_count is None and profile.average_views is None and profile.engagement_rate is None
    assert len(profile.warnings) >= 5


def test_duplicate_profiles_use_platform_id_not_handle():
    base = {"id": "1", "entity_type": "creator", "username": "same", "collected_at": "2026-01-01T00:00:00Z"}
    a = normalize_payload(Platform.X, base, "mock:x")
    duplicate = normalize_payload(Platform.X, dict(base, display_name="duplicate"), "mock:x")
    cross_platform = normalize_payload(Platform.YOUTUBE, base, "mock:youtube")
    result = deduplicate_profiles([a, duplicate, cross_platform])
    assert len(result) == 2


def test_identity_linking_is_conservative_and_never_name_based():
    common = {"entity_type": "creator", "display_name": "Same Name", "collected_at": "2026-01-01T00:00:00Z"}
    left = normalize_payload(Platform.X, dict(common, id="1", username="shared"), "mock:x")
    right = normalize_payload(Platform.YOUTUBE, dict(common, id="2", username="shared"), "mock:youtube")
    username_only = suggest_identity(left, right)
    assert username_only.confidence == 0.70 and not username_only.automatic_merge_allowed
    unrelated = right.model_copy(update={"username": "different"})
    assert suggest_identity(left, unrelated).confidence == 0
    same_site = unrelated.model_copy(update={"website": "https://owner.example"})
    left_site = left.model_copy(update={"website": "https://owner.example"})
    assert suggest_identity(left_site, same_site).automatic_merge_allowed


def test_ranking_is_deterministic_and_missing_is_not_zero():
    criteria = DiscoveryCriteria(platforms=["snapchat"], minimum_followers=1000, minimum_engagement_rate=2)
    profile = run(build_mock_adapters()[Platform.SNAPCHAT].search_creators(criteria))[0]
    first, second = rank_profile(profile, criteria), rank_profile(profile, criteria)
    assert first == second
    assert first.score_components.follower_range_match is None
    assert first.score_components.engagement_match is None
    assert first.score > 0
    assert any("not scored" in warning for warning in first.warnings)


async def authenticated_client(monkeypatch, role=None):
    mongo = AsyncMongoMockClient()
    database = mongo[f"multi_{role or 'anonymous'}"]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    security._RL_BUCKETS.clear()
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
    if role:
        now = datetime.now(timezone.utc)
        result = await database.users.insert_one({"email": f"{role}@example.com", "name": role, "role": role, "status": "active", "email_verified": True, "created_at": now, "updated_at": now})
        client.cookies.set("access_token", server.create_access_token(str(result.inserted_id), f"{role}@example.com", role))
    return mongo, database, client


@pytest.mark.parametrize("role,status", [(None, 401), ("influencer", 403), ("brand", 200), ("admin", 200)])
def test_endpoint_authentication_and_roles(monkeypatch, role, status):
    async def scenario():
        mongo, _, client = await authenticated_client(monkeypatch, role)
        try:
            response = await client.post("/api/ai/discovery/preview", json={"entity_type": "creator", "platforms": ["instagram"]})
            assert response.status_code == status, response.text
        finally:
            await client.aclose(); mongo.close()
    run(scenario())


def test_endpoint_has_source_attribution_and_writes_no_database(monkeypatch):
    async def scenario():
        mongo, database, client = await authenticated_client(monkeypatch, "brand")
        try:
            before = {name: await database[name].count_documents({}) for name in await database.list_collection_names()}
            response = await client.post("/api/ai/discovery/preview", json={"entity_type": "both", "platforms": ["instagram", "youtube"], "result_limit": 6})
            after = {name: await database[name].count_documents({}) for name in await database.list_collection_names()}
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["mock_mode"] is True and body["sources"] == ["mock:instagram", "mock:youtube"]
            assert {item["profile"]["entity_type"] for item in body["results"]} == {"creator", "brand"}
            assert before == after
        finally:
            await client.aclose(); mongo.close()
    run(scenario())


def test_existing_preview_route_remains_registered():
    paths = server.app.openapi()["paths"]
    assert "/api/ai/brand-discovery/preview" in paths
    assert "/api/ai/discovery/preview" in paths
