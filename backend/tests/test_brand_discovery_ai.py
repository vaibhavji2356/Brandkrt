import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from brand_discovery_ai.config import AISettings
from brand_discovery_ai.errors import AIProviderUnavailableError, RetryableProviderError
from brand_discovery_ai.providers import BrandDiscoveryProvider
from brand_discovery_ai.router import get_brand_discovery_service
from brand_discovery_ai.service import BrandDiscoveryService


VALID_REQUEST = {
    "industry": "  sustainable   fashion ",
    "location": " India ",
    "target_audience": "urban Gen Z shoppers",
    "campaign_objective": "creator-led awareness",
    "preferred_platforms": [" Instagram ", "YouTube"],
    "keywords": ["ethical materials", "slow fashion"],
    "result_limit": 3,
}


async def _client_context(monkeypatch, name: str, role: str | None):
    mongo = AsyncMongoMockClient()
    database = mongo[name]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_MOCK_MODE", "true")
    security._RL_BUCKETS.clear()

    transport = httpx.ASGITransport(app=server.app)
    client = httpx.AsyncClient(transport=transport, base_url="https://brandkrt.com")
    if role is not None:
        now = datetime.now(timezone.utc)
        inserted = await database.users.insert_one({
            "email": f"{role}-{name}@example.com",
            "name": role,
            "role": role,
            "status": "active",
            "email_verified": True,
            "created_at": now,
            "updated_at": now,
        })
        client.cookies.set(
            "access_token",
            server.create_access_token(str(inserted.inserted_id), f"{role}-{name}@example.com", role),
        )
    return mongo, database, client


def _settings(*, timeout: float = 1.0, retries: int = 0) -> AISettings:
    return AISettings(
        provider="mock",
        timeout_seconds=timeout,
        max_retries=retries,
        mock_mode=True,
    )


def test_unauthenticated_request_is_rejected(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_unauthenticated", None)
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert response.status_code == 401
            assert response.json()["detail"] == "Not authenticated"
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_unauthorized_role_is_rejected(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_wrong_role", "influencer")
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert response.status_code == 403
            assert response.json()["detail"] == "Forbidden"
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_valid_mock_request_succeeds_and_normalizes_input(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_mock_success", "brand")
        try:
            first = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            second = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert first.status_code == 200, first.text
            assert first.json() == second.json()
            body = first.json()
            assert body["count"] == 3
            assert body["provider"] == "mock"
            assert body["mock_mode"] is True
            assert len(body["results"]) == 3
            assert body["results"][0]["industry"] == "sustainable fashion"
            assert body["results"][0]["source_type"] == "mock"
            assert 0 <= body["results"][0]["relevance_score"] <= 100
            assert 0 <= body["results"][0]["confidence_score"] <= 100
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_invalid_budget_range_is_rejected(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_bad_budget", "brand")
        try:
            response = await client.post(
                "/api/ai/brand-discovery/preview",
                json={"industry": "beauty", "minimum_budget": 50_000, "maximum_budget": 10_000},
            )
            assert response.status_code == 422
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_empty_request_is_rejected(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_empty_request", "brand")
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json={})
            assert response.status_code == 422
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_result_limit_is_enforced(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_result_limit", "brand")
        try:
            maximum = await client.post(
                "/api/ai/brand-discovery/preview",
                json={"industry": "fitness", "result_limit": 20},
            )
            over_limit = await client.post(
                "/api/ai/brand-discovery/preview",
                json={"industry": "fitness", "result_limit": 21},
            )
            assert maximum.status_code == 200, maximum.text
            assert maximum.json()["count"] == 20
            assert len(maximum.json()["results"]) == 20
            assert over_limit.status_code == 422
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


class _MalformedProvider(BrandDiscoveryProvider):
    name = "test-malformed"

    async def generate(self, *, prompt, request):
        del prompt, request
        return {"results": [{"brand_name": "provider-private-payload"}]}


def test_malformed_provider_output_is_rejected_safely(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_malformed", "brand")
        service = BrandDiscoveryService(_settings(), _MalformedProvider())
        server.app.dependency_overrides[get_brand_discovery_service] = lambda: service
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert response.status_code == 502
            assert response.json()["detail"]["code"] == "ai_invalid_response"
            assert "provider-private-payload" not in response.text
        finally:
            server.app.dependency_overrides.pop(get_brand_discovery_service, None)
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


class _SlowProvider(BrandDiscoveryProvider):
    name = "test-slow"

    async def generate(self, *, prompt, request):
        del prompt, request
        await asyncio.sleep(1.1)
        return {"results": []}


def test_provider_timeout_is_mapped_safely(monkeypatch):
    async def scenario():
        mongo, _database, client = await _client_context(monkeypatch, "ai_timeout", "brand")
        service = BrandDiscoveryService(_settings(timeout=1.0), _SlowProvider())
        server.app.dependency_overrides[get_brand_discovery_service] = lambda: service
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert response.status_code == 504
            assert response.json()["detail"]["code"] == "ai_provider_timeout"
            assert "Traceback" not in response.text
        finally:
            server.app.dependency_overrides.pop(get_brand_discovery_service, None)
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


class _RetryProvider(BrandDiscoveryProvider):
    name = "test-retry"

    def __init__(self):
        self.calls = 0

    async def generate(self, *, prompt, request):
        del prompt, request
        self.calls += 1
        raise RetryableProviderError("internal provider detail")


def test_retry_limit_is_respected():
    async def scenario():
        provider = _RetryProvider()
        service = BrandDiscoveryService(_settings(retries=1), provider)
        from brand_discovery_ai.schemas import BrandDiscoveryRequest

        with pytest.raises(AIProviderUnavailableError):
            await service.preview(BrandDiscoveryRequest(industry="technology"))
        assert provider.calls == 2

    asyncio.run(scenario())


class _SecretFailureProvider(BrandDiscoveryProvider):
    name = "test-secret"

    def __init__(self, secret: str):
        self.secret = secret

    async def generate(self, *, prompt, request):
        del prompt, request
        raise RuntimeError(f"upstream failure included {self.secret}")


def test_secrets_are_not_in_logs_or_response(monkeypatch, caplog):
    async def scenario():
        secret = "sk-test-super-secret-provider-key"
        monkeypatch.setenv("AI_API_KEY", secret)
        mongo, _database, client = await _client_context(monkeypatch, "ai_secret_redaction", "brand")
        service = BrandDiscoveryService(_settings(), _SecretFailureProvider(secret))
        server.app.dependency_overrides[get_brand_discovery_service] = lambda: service
        caplog.set_level(logging.WARNING, logger="brandkrt.ai")
        try:
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "ai_provider_unavailable"
            assert secret not in response.text
            assert secret not in caplog.text
            assert "upstream failure included" not in caplog.text
        finally:
            server.app.dependency_overrides.pop(get_brand_discovery_service, None)
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())


def test_preview_creates_no_database_records(monkeypatch):
    async def scenario():
        mongo, database, client = await _client_context(monkeypatch, "ai_no_persistence", "admin")
        try:
            before_names = await database.list_collection_names()
            before_counts = {name: await database[name].count_documents({}) for name in before_names}
            response = await client.post("/api/ai/brand-discovery/preview", json=VALID_REQUEST)
            after_names = await database.list_collection_names()
            after_counts = {name: await database[name].count_documents({}) for name in after_names}

            assert response.status_code == 200, response.text
            assert set(after_names) == set(before_names)
            assert after_counts == before_counts
        finally:
            await client.aclose()
            mongo.close()

    asyncio.run(scenario())
