import asyncio
import json
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.config import AISettings
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria
from creator_intelligence.engine import CreatorIntelligenceEngine
from creator_intelligence.models import CreatorIntelligenceRequest
from creator_intelligence.narrative import CreatorNarrativeService, deterministic_fallback_narrative
from creator_intelligence.narrative_provider import (
    CreatorNarrativeProvider, NarrativeProviderError, OpenAICreatorNarrativeProvider,
)
from research_agent.agent import ResearchAgent


def run(coro):
    return asyncio.run(coro)


def request_and_result(*, include=True):
    package = run(ResearchAgent().research(DiscoveryCriteria(
        entity_type="creator", platforms=["instagram"], niche="fitness", result_limit=5,
    ))).package
    request = CreatorIntelligenceRequest(
        research_package=package, campaign_budget=1000, number_of_creators=2,
        campaign_objective="Brand Awareness", include_ai_narrative=include,
    )
    return request, CreatorIntelligenceEngine().recommend(request)


def valid_payload(request, result):
    return deterministic_fallback_narrative(request, result).model_dump(mode="json")


class StaticProvider(CreatorNarrativeProvider):
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def narrate(self, prompt):
        self.calls += 1
        return self.payload


class FailingProvider(CreatorNarrativeProvider):
    def __init__(self, message="private raw provider response"):
        self.message = message
        self.calls = 0

    async def narrate(self, prompt):
        self.calls += 1
        raise NarrativeProviderError(self.message)


class TimeoutProvider(CreatorNarrativeProvider):
    async def narrate(self, prompt):
        raise asyncio.TimeoutError()


def test_narrative_disabled_makes_no_provider_call_and_keeps_compatibility():
    request, result = request_and_result(include=False)
    provider = StaticProvider({"invalid": True})
    enriched = run(CreatorNarrativeService(provider).enrich(request, result))
    assert provider.calls == 0
    assert enriched.ai_narrative is None
    assert enriched.narrative_source == "disabled"
    assert enriched.model_dump(exclude={"ai_narrative", "narrative_source", "narrative_degraded"}) == result.model_dump(
        exclude={"ai_narrative", "narrative_source", "narrative_degraded"}
    )


def test_valid_structured_narrative_is_accepted_with_one_call():
    request, result = request_and_result()
    provider = StaticProvider(valid_payload(request, result))
    enriched = run(CreatorNarrativeService(provider).enrich(request, result))
    assert provider.calls == 1
    assert enriched.narrative_source == "openai_grounded"
    assert enriched.narrative_degraded is False
    assert [item.profile_reference for item in enriched.ai_narrative.creator_narratives] == result.ranking


def test_malformed_output_returns_deterministic_fallback():
    request, result = request_and_result()
    enriched = run(CreatorNarrativeService(StaticProvider({"unexpected": []})).enrich(request, result))
    assert enriched.narrative_source == "deterministic_fallback"
    assert enriched.narrative_degraded is True
    assert enriched.ai_narrative.creator_narratives


def test_unknown_creator_and_modified_ranking_are_rejected():
    request, result = request_and_result()
    unknown = valid_payload(request, result)
    unknown["creator_narratives"][0]["profile_reference"] = "youtube:unknown"
    first = run(CreatorNarrativeService(StaticProvider(unknown)).enrich(request, result))
    assert first.narrative_source == "deterministic_fallback"

    reordered = valid_payload(request, result)
    reordered["creator_narratives"].reverse()
    second = run(CreatorNarrativeService(StaticProvider(reordered)).enrich(request, result))
    assert second.narrative_source == "deterministic_fallback"


def test_modified_rate_and_currency_are_rejected():
    request, result = request_and_result()
    payload = valid_payload(request, result)
    # 1000 is a real budget value but not this creator's rate; semantic grounding must still reject it.
    payload["creator_narratives"][0]["pricing_assessment"] = "The selected rate is 1000 EUR."
    enriched = run(CreatorNarrativeService(StaticProvider(payload)).enrich(request, result))
    assert enriched.narrative_source == "deterministic_fallback"
    assert enriched.ai_narrative.creator_narratives[0].pricing_assessment != "The selected rate is 1000 EUR."


def test_fabricated_metric_and_unsupported_guarantee_are_rejected():
    request, result = request_and_result()
    metric = valid_payload(request, result)
    metric["creator_narratives"][0]["selection_reason"] = "Expected reach is 123456."
    metric_result = run(CreatorNarrativeService(StaticProvider(metric)).enrich(request, result))
    assert metric_result.narrative_source == "deterministic_fallback"
    assert "123456" not in metric_result.model_dump_json()

    guarantee = valid_payload(request, result)
    guarantee["executive_summary"] = "The portfolio guarantees campaign success."
    guarantee_result = run(CreatorNarrativeService(StaticProvider(guarantee)).enrich(request, result))
    assert guarantee_result.narrative_source == "deterministic_fallback"


def test_timeout_provider_failure_and_unconfigured_provider_use_safe_fallback():
    request, result = request_and_result()
    for provider in (TimeoutProvider(), FailingProvider(), None):
        enriched = run(CreatorNarrativeService(provider).enrich(request, result))
        assert enriched.narrative_source == "deterministic_fallback"
        assert enriched.ai_narrative is not None


def test_fallback_bounds_untrusted_warning_text():
    request, result = request_and_result()
    result = result.model_copy(update={"warnings": ["x" * 2000]})
    enriched = run(CreatorNarrativeService().enrich(request, result))
    assert enriched.narrative_source == "deterministic_fallback"
    assert len(enriched.ai_narrative.warnings[0]) <= 500


def test_raw_provider_error_is_not_exposed_and_deterministic_result_is_unchanged():
    request, result = request_and_result()
    enriched = run(CreatorNarrativeService(FailingProvider("secret raw output 123456")).enrich(request, result))
    assert "secret raw output" not in enriched.model_dump_json().casefold()
    authoritative_fields = {"recommendations", "ranking", "pricing_analysis", "budget_analysis", "roi_analysis", "confidence"}
    before = result.model_dump()
    after = enriched.model_dump()
    assert all(after[field] == before[field] for field in authoritative_fields)


def test_openai_adapter_uses_strict_schema_and_one_mocked_http_call():
    request, result = request_and_result()
    expected = valid_payload(request, result)
    calls = []

    async def handler(http_request):
        calls.append(http_request)
        return httpx.Response(200, json={"output_text": json.dumps(expected)})

    settings = AISettings(
        provider="openai", api_key="test-key", model="gpt-5.6-luna",
        allowed_models=("gpt-5.6-luna",), timeout_seconds=2, max_retries=1,
        max_output_tokens=2000, mock_mode=False,
    )
    provider = OpenAICreatorNarrativeProvider(settings, httpx.MockTransport(handler))
    enriched = run(CreatorNarrativeService(provider).enrich(request, result))
    assert enriched.narrative_source == "openai_grounded"
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert body["store"] is False
    assert body["text"]["format"]["strict"] is True
