import asyncio
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from mongomock_motor import AsyncMongoMockClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import admin_lead_intelligence.router as lead_router
import security
from admin_lead_intelligence.repository import create_admin_lead_indexes
from match_intelligence.engine import MatchEngine
from operations.rate_limiting import InMemoryRateLimitBackend, rate_limiter
from research_agent.agent import ResearchAgent


CREATOR_REQUEST = {
    "research_name": "Sustainable creator search",
    "entity_type": "creator",
    "platforms": ["instagram"],
    "niche": "sustainable fashion",
    "categories": ["lifestyle"],
    "keywords": ["ethical"],
    "location": "Mumbai, India",
    "language": "en",
    "minimum_followers": 1000,
    "minimum_engagement_rate": 1,
    "campaign_objective": "Brand Awareness",
    "maximum_budget": 10000,
    "currency": "USD",
    "result_limit": 5,
}

BRAND_REQUEST = {
    "research_name": "Sustainable brand search",
    "entity_type": "brand",
    "platforms": ["instagram"],
    "industry": "sustainable fashion",
    "keywords": ["ethical"],
    "location": "Mumbai, India",
    "language": "en",
    "result_limit": 5,
}


async def _context(monkeypatch):
    database = AsyncMongoMockClient()["admin_lead_test"]
    await create_admin_lead_indexes(database)
    monkeypatch.setattr(lead_router, "get_admin_research_agent", lambda: ResearchAgent())
    monkeypatch.setattr(lead_router, "get_match_engine", lambda: MatchEngine())
    rate_limiter.configure(InMemoryRateLimitBackend())
    security._RL_BUCKETS.clear()

    async def current_user(request: Request):
        role = request.headers.get("x-test-role")
        if not role:
            raise HTTPException(status_code=401, detail="Authentication required")
        return {"_id": f"{role}-user", "role": role, "email": f"{role}@example.com"}

    app = FastAPI()
    app.include_router(lead_router.create_admin_lead_router(current_user, lambda: database), prefix="/api")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://brandkrt.test")
    return database, client


async def _create_completed(client, payload=CREATOR_REQUEST):
    response = await client.post(
        "/api/admin/lead-intelligence/research/jobs", json=payload,
        headers={"x-test-role": "admin"},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    detail = await client.get(
        f"/api/admin/lead-intelligence/research/jobs/{job_id}",
        headers={"x-test-role": "admin"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "completed"
    return detail.json()


def test_every_endpoint_is_admin_only(monkeypatch):
    async def scenario():
        _database, client = await _context(monkeypatch)
        try:
            path = "/api/admin/lead-intelligence/analytics"
            assert (await client.get(path)).status_code == 401
            assert (await client.get(path, headers={"x-test-role": "brand"})).status_code == 403
            assert (await client.get(path, headers={"x-test-role": "creator"})).status_code == 403
            assert (await client.get(path, headers={"x-test-role": "admin"})).status_code == 200
        finally:
            await client.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize("payload,entity_type", [(CREATOR_REQUEST, "creator"), (BRAND_REQUEST, "brand")])
def test_research_job_returns_grounded_normalized_results(monkeypatch, payload, entity_type):
    async def scenario():
        _database, client = await _context(monkeypatch)
        try:
            detail = await _create_completed(client, payload)
            assert detail["progress"] == 100
            assert detail["result_count"] > 0
            assert "ai_context" not in detail
            assert "tasks" not in detail
            result = detail["results"][0]
            assert result["entity_type"] == entity_type
            assert result["discovery_source"].startswith("mock:")
            assert 0 <= result["recommendation_score"] <= 100
            assert result["priority"]["explanation"]
            assert result["assistance"]["why_contact"]
            assert result["last_observed_activity"] is None
            assert result["audience_quality"] is None
            assert "password" not in str(detail).casefold()
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_creator_research_enforces_follower_and_inr_budget_ranges(monkeypatch):
    async def scenario():
        _database, client = await _context(monkeypatch)
        try:
            follower_payload = {
                **CREATOR_REQUEST, "minimum_followers": 31_000,
                "maximum_followers": 35_000, "maximum_budget": 1_000,
                "currency": "INR",
            }
            follower_detail = await _create_completed(client, follower_payload)
            assert [item["follower_count"] for item in follower_detail["results"]] == [35_000]
            assert all(item["pricing"]["currency"] == "INR" for item in follower_detail["results"])
            assert any("outside the requested follower range" in item for item in follower_detail["warnings"])

            budget_payload = {
                **CREATOR_REQUEST, "maximum_followers": 50_000,
                "maximum_budget": 50, "currency": "INR",
            }
            budget_detail = await _create_completed(client, budget_payload)
            assert budget_detail["result_count"] == 0
            assert any("outside the requested INR budget range" in item for item in budget_detail["warnings"])
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_research_history_filters_and_reruns(monkeypatch):
    async def scenario():
        _database, client = await _context(monkeypatch)
        try:
            original = await _create_completed(client)
            history = await client.get(
                "/api/admin/lead-intelligence/research/history",
                params={"entity_type": "creator", "platform": "instagram", "search": "Sustainable"},
                headers={"x-test-role": "admin"},
            )
            assert history.status_code == 200
            assert history.json()["total"] == 1
            rerun = await client.post(
                f"/api/admin/lead-intelligence/research/history/{original['id']}/rerun",
                headers={"x-test-role": "admin"},
            )
            assert rerun.status_code == 202
            assert rerun.json()["id"] != original["id"]
            rerun_detail = await client.get(
                f"/api/admin/lead-intelligence/research/jobs/{rerun.json()['id']}",
                headers={"x-test-role": "admin"},
            )
            assert rerun_detail.json()["status"] == "completed"
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_saved_lead_workflow_deduplicates_and_audits_without_note_content(monkeypatch):
    async def scenario():
        database, client = await _context(monkeypatch)
        try:
            detail = await _create_completed(client)
            payload = {"research_id": detail["id"], "entity_key": detail["results"][0]["entity_key"]}
            first = await client.post(
                "/api/admin/lead-intelligence/leads", json=payload,
                headers={"x-test-role": "admin"},
            )
            second = await client.post(
                "/api/admin/lead-intelligence/leads", json=payload,
                headers={"x-test-role": "admin"},
            )
            assert first.status_code == second.status_code == 200
            assert first.json()["id"] == second.json()["id"]
            lead_id = first.json()["id"]

            updated = await client.patch(
                f"/api/admin/lead-intelligence/leads/{lead_id}", json={"status": "contacted"},
                headers={"x-test-role": "admin"},
            )
            assert updated.json()["status"] == "contacted"
            noted = await client.post(
                f"/api/admin/lead-intelligence/leads/{lead_id}/notes",
                json={"note": "Private negotiation context for admin review."},
                headers={"x-test-role": "admin"},
            )
            assert noted.json()["notes"][0]["note"].startswith("Private negotiation")
            audit = await client.get(
                f"/api/admin/lead-intelligence/leads/{lead_id}/audit",
                headers={"x-test-role": "admin"},
            )
            assert audit.status_code == 200
            assert "Private negotiation" not in audit.text
            assert await database.admin_saved_leads.count_documents({}) == 1
            archived = await client.post(
                f"/api/admin/lead-intelligence/leads/{lead_id}/archive",
                headers={"x-test-role": "admin"},
            )
            assert archived.json()["archived"] is True
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_lead_search_sort_pagination_and_analytics(monkeypatch):
    async def scenario():
        _database, client = await _context(monkeypatch)
        try:
            detail = await _create_completed(client)
            for result in detail["results"]:
                await client.post(
                    "/api/admin/lead-intelligence/leads",
                    json={"research_id": detail["id"], "entity_key": result["entity_key"]},
                    headers={"x-test-role": "admin"},
                )
            page = await client.get(
                "/api/admin/lead-intelligence/leads",
                params={"search": "Creator", "entity_type": "creator", "sort_by": "priority", "page_size": 1},
                headers={"x-test-role": "admin"},
            )
            assert page.status_code == 200
            assert len(page.json()["items"]) == 1
            assert page.json()["total"] >= 1
            analytics = await client.get(
                "/api/admin/lead-intelligence/analytics", headers={"x-test-role": "admin"},
            )
            assert analytics.json()["creators_found"] >= 1
            assert analytics.json()["saved_leads"] >= 1
            assert analytics.json()["top_platforms"][0]["name"] == "instagram"
            activity = await client.get(
                "/api/admin/lead-intelligence/activity", headers={"x-test-role": "admin"},
            )
            assert activity.json()["items"][0]["reasoning_source"] == "deterministic_fallback"
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_failed_research_is_safe_and_retryable(monkeypatch):
    class FailingAgent:
        async def research(self, _criteria):
            raise RuntimeError("provider-secret-detail")

    async def scenario():
        _database, client = await _context(monkeypatch)
        monkeypatch.setattr(lead_router, "get_admin_research_agent", lambda: FailingAgent())
        try:
            response = await client.post(
                "/api/admin/lead-intelligence/research/jobs", json=CREATOR_REQUEST,
                headers={"x-test-role": "admin"},
            )
            detail = await client.get(
                f"/api/admin/lead-intelligence/research/jobs/{response.json()['id']}",
                headers={"x-test-role": "admin"},
            )
            assert detail.json()["status"] == "failed"
            assert detail.json()["error_code"] == "research_failed"
            assert "provider-secret-detail" not in detail.text
        finally:
            await client.aclose()
    asyncio.run(scenario())


def test_admin_lead_indexes_are_idempotent(monkeypatch):
    async def scenario():
        database = AsyncMongoMockClient()["admin_lead_indexes"]
        await create_admin_lead_indexes(database)
        await create_admin_lead_indexes(database)
        lead_indexes = await database.admin_saved_leads.index_information()
        assert lead_indexes["admin_saved_lead_fingerprint"]["unique"] is True
        assert "admin_research_status_created" in await database.admin_research_jobs.index_information()
    asyncio.run(scenario())
