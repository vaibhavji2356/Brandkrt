import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
from mongomock_motor import AsyncMongoMockClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import security
import server
from brand_discovery_ai.config import AISettings
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria
from match_intelligence.engine import MatchEngine
from match_intelligence.models import RecommendationCategory
from match_intelligence.prompting import build_match_prompt
from match_intelligence.provider import MatchProviderError, MatchReasoningProvider, OpenAIMatchReasoningProvider
from match_intelligence.router import get_match_engine
from research_agent.agent import ResearchAgent


def run(coro):
    return asyncio.run(coro)


def package(*, score=80, objective="Product launch awareness", platform="instagram"):
    result = run(ResearchAgent().research(DiscoveryCriteria(
        entity_type="creator", platforms=[platform], niche="fitness",
        campaign_objective=objective, result_limit=5,
    )))
    rankings = [item.model_copy(update={"score": score}) for item in result.package.ranking_summary]
    return result.package.model_copy(update={"ranking_summary": rankings})


def qualitative_payload(pkg, *, hallucination=False, identity_hallucination=False):
    recommendations = []
    for index, profile in enumerate(pkg.normalized_entities):
        if profile.entity_type != "creator":
            continue
        ref = f"{profile.platform.value}:{profile.platform_id}"
        recommendations.append({
            "profile_reference": ref,
            "ai_confidence": 88,
            "recommendation_summary": (
                "This creator has 1 million followers." if hallucination
                else "This is a verified creator based in India." if identity_hallucination
                else f"Creator {index + 1} has relevant validated positioning signals."
            ),
            "why_recommended": [f"Validated category evidence supports creator option {index + 1}."],
            "strengths": [f"Source-backed positioning is available for option {index + 1}."],
            "weaknesses": ["Insufficient verified data."],
            "campaign_fit": f"A controlled campaign pilot is appropriate for option {index + 1}.",
            "audience_fit": "Insufficient verified data.",
            "niche_fit": f"Available niche evidence supports evaluation of option {index + 1}.",
            "budget_fit": "Insufficient verified data.",
            "platform_fit": f"The supplied platform matches the request for option {index + 1}.",
            "marketing_intelligence": {
                "target_audience_overlap": "Insufficient verified data.",
                "brand_positioning_compatibility": f"Positioning evidence is directionally compatible for option {index + 1}.",
                "expected_campaign_style": f"Use an educational concept for option {index + 1}.",
                "estimated_collaboration_quality": f"Validate delivery quality through a scoped pilot for option {index + 1}.",
                "long_term_partnership_potential": f"Review pilot outcomes before a longer agreement for option {index + 1}.",
            },
            "campaign_strategy": {
                "campaign_type": "Product Launch", "campaign_goal": f"Build qualified awareness with option {index + 1}.",
                "content_style": "Educational",
            },
            "outreach": {
                "first_contact_angle": f"Reference the creator's relevant content focus for option {index + 1}.",
                "collaboration_pitch": f"Invite option {index + 1} to review a scoped launch brief.",
                "value_proposition": f"Offer clear scope and creative input for option {index + 1}.",
                "call_to_action": f"Ask whether option {index + 1} is open to reviewing the brief.",
            },
            "risks": [{"risk_type": "insufficient information", "explanation": f"Pricing requires confirmation for option {index + 1}."}],
        })
    return {"recommendations": recommendations}


class StaticProvider(MatchReasoningProvider):
    def __init__(self, value): self.value = value; self.calls = 0
    async def reason(self, prompt):
        self.calls += 1
        return self.value


class FailingProvider(MatchReasoningProvider):
    async def reason(self, prompt):
        raise MatchProviderError("private provider detail")


def test_excellent_recommendation_uses_authoritative_ranking_score():
    pkg = package(score=91)
    response = run(MatchEngine(StaticProvider(qualitative_payload(pkg))).recommend(pkg))
    assert response.degraded is False
    assert response.recommendations
    assert all(item.overall_match_score == 91 for item in response.recommendations)
    assert all(item.recommendation_category == RecommendationCategory.EXCELLENT for item in response.recommendations)
    assert all(item.ai_confidence <= pkg.confidence * 100 for item in response.recommendations)


def test_weak_recommendation_is_deterministic():
    pkg = package(score=30)
    first = run(MatchEngine().recommend(pkg))
    second = run(MatchEngine().recommend(pkg))
    assert first == second
    assert all(item.recommendation_category == RecommendationCategory.WEAK for item in first.recommendations)


def test_campaign_generation_uses_campaign_objective():
    response = run(MatchEngine().recommend(package(objective="Launch a new fitness product")))
    recommendation = response.recommendations[0]
    assert recommendation.campaign_strategy.campaign_type == "Product Launch"
    assert "Launch a new fitness product" in recommendation.campaign_strategy.campaign_goal
    assert recommendation.campaign_strategy.content_style


def test_risk_engine_explains_missing_data_and_budget():
    response = run(MatchEngine().recommend(package(platform="snapchat")))
    risks = response.recommendations[0].risks
    assert any(item.risk_type == "missing metrics" and item.explanation for item in risks)
    assert any(item.risk_type == "budget mismatch" and item.explanation for item in risks)
    assert response.recommendations[0].audience_fit == "Insufficient verified data."


def test_outreach_is_professional_and_has_clear_call_to_action():
    outreach = run(MatchEngine().recommend(package())).recommendations[0].outreach
    assert "brief" in outreach.collaboration_pitch.casefold()
    assert "ask whether" in outreach.call_to_action.casefold()
    assert "buy now" not in outreach.model_dump_json().casefold()


def test_provider_failure_returns_graceful_fallback():
    response = run(MatchEngine(FailingProvider()).recommend(package()))
    assert response.degraded is True
    assert response.reasoning_source == "deterministic_fallback"
    assert response.recommendations
    assert all("private provider detail" not in warning for warning in response.warnings)


def test_invalid_provider_response_returns_fallback():
    response = run(MatchEngine(StaticProvider({"unexpected": []})).recommend(package()))
    assert response.degraded is True and response.recommendations


def test_hallucinated_metric_is_rejected_and_not_returned():
    pkg = package()
    response = run(MatchEngine(StaticProvider(qualitative_payload(pkg, hallucination=True))).recommend(pkg))
    assert response.degraded is True
    serialized = response.model_dump_json().casefold()
    assert "1 million followers" not in serialized


def test_hallucinated_identity_and_country_are_rejected():
    pkg = package()
    response = run(MatchEngine(StaticProvider(qualitative_payload(pkg, identity_hallucination=True))).recommend(pkg))
    assert response.degraded is True
    assert "verified creator based in india" not in response.model_dump_json().casefold()


def test_one_provider_call_handles_whole_package():
    pkg = package()
    provider = StaticProvider(qualitative_payload(pkg))
    response = run(MatchEngine(provider).recommend(pkg))
    assert response.degraded is False and provider.calls == 1


def test_openai_provider_uses_structured_output_with_mocked_transport():
    pkg = package()
    expected = qualitative_payload(pkg)
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"output_text": __import__("json").dumps(expected)})
    settings = AISettings(
        provider="openai", api_key="test-key", model="gpt-5.6-luna",
        allowed_models=("gpt-5.6-luna",), timeout_seconds=2, max_retries=0,
        max_output_tokens=1000, mock_mode=False,
    )
    provider = OpenAIMatchReasoningProvider(settings, http_transport=httpx.MockTransport(handler))
    result = run(provider.reason(build_match_prompt(pkg)))
    assert result == expected and len(calls) == 1
    body = __import__("json").loads(calls[0].content)
    assert body["store"] is False
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["verbosity"] == "low"


async def authenticated_client(monkeypatch):
    mongo = AsyncMongoMockClient()
    database = mongo["match_endpoint"]
    monkeypatch.setattr(server, "db", database)
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-with-more-than-32-characters")
    security._RL_BUCKETS.clear()
    now = datetime.now(timezone.utc)
    inserted = await database.users.insert_one({
        "email": "brand-match@example.com", "name": "brand", "role": "brand",
        "status": "active", "email_verified": True, "created_at": now, "updated_at": now,
    })
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="https://brandkrt.test")
    client.cookies.set("access_token", server.create_access_token(str(inserted.inserted_id), "brand-match@example.com", "brand"))
    return mongo, client


def test_endpoint_returns_200_when_openai_fails(monkeypatch):
    pkg = package()
    async def scenario():
        mongo, client = await authenticated_client(monkeypatch)
        server.app.dependency_overrides[get_match_engine] = lambda: MatchEngine(FailingProvider())
        try:
            response = await client.post("/api/ai/match/recommendations", json=pkg.model_dump(mode="json"))
            assert response.status_code == 200, response.text
            assert response.json()["degraded"] is True
            assert response.json()["recommendations"]
        finally:
            server.app.dependency_overrides.pop(get_match_engine, None)
            await client.aclose(); mongo.close()
    run(scenario())
