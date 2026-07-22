"""One-pass grounded reasoning with deterministic graceful degradation."""

import json

from brand_discovery_ai.costing import (
    CONSERVATIVE_INPUT_PRICE_MULTIPLIER, MODEL_PRICING_USD_PER_MTOK,
    estimate_text_tokens,
)
from brand_discovery_ai.usage import UsageIdentity, ai_usage_accounting
from research_agent.models import ResearchPackage

from .fallback import category_for_score, deterministic_recommendations
from .grounding import validate_provider_payload
from .models import CreatorRecommendation, MatchIntelligenceResponse, ProviderPayload
from .prompting import build_match_prompt
from .provider import MatchReasoningProvider, OpenAIMatchReasoningProvider, provider_response_schema


class MatchEngine:
    def __init__(self, provider: MatchReasoningProvider | None = None):
        self.provider = provider

    async def recommend(
        self,
        package: ResearchPackage,
        *,
        usage_identity: UsageIdentity | None = None,
    ) -> MatchIntelligenceResponse:
        fallback = deterministic_recommendations(package)
        if self.provider is None or not fallback:
            return _fallback_response(package, fallback, "AI reasoning unavailable; deterministic recommendations returned.")
        prompt = build_match_prompt(package)
        try:
            _reserve_if_paid(self.provider, prompt, usage_identity)
            raw = await self.provider.reason(prompt)
            payload = ProviderPayload.model_validate(raw)
            expected = [item.profile_reference for item in fallback]
            validate_provider_payload(payload, expected)
            base_by_reference = {item.profile_reference: item for item in fallback}
            provider_by_reference = {item.profile_reference: item for item in payload.recommendations}
            recommendations = []
            for reference in expected:
                base = base_by_reference[reference]
                qualitative = provider_by_reference[reference]
                data = qualitative.model_dump()
                data["ai_confidence"] = min(qualitative.ai_confidence, base.ai_confidence)
                recommendations.append(CreatorRecommendation(
                    **data,
                    overall_match_score=base.overall_match_score,
                    recommendation_category=category_for_score(base.overall_match_score),
                ))
            return MatchIntelligenceResponse(
                recommendations=recommendations, count=len(recommendations), degraded=False,
                reasoning_source="openai_grounded", warnings=list(package.warnings),
            )
        except Exception:
            return _fallback_response(
                package, fallback,
                "AI reasoning failed validation or was unavailable; deterministic recommendations returned.",
            )


def _fallback_response(package, recommendations, warning):
    return MatchIntelligenceResponse(
        recommendations=recommendations, count=len(recommendations), degraded=True,
        reasoning_source="deterministic_fallback",
        warnings=list(dict.fromkeys([*package.warnings, warning])),
    )


def _reserve_if_paid(provider, prompt, identity):
    if not isinstance(provider, OpenAIMatchReasoningProvider):
        return
    settings = provider.settings
    prices = MODEL_PRICING_USD_PER_MTOK.get(settings.model)
    if prices is None:
        raise ValueError("Model pricing is unavailable.")
    serialized_prompt = json.dumps(prompt.as_messages(), ensure_ascii=False, separators=(",", ":"))
    serialized_schema = json.dumps(provider_response_schema(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    input_tokens = estimate_text_tokens(serialized_prompt) + estimate_text_tokens(serialized_schema)
    input_price, output_price = prices
    per_attempt = (
        input_tokens * input_price * CONSERVATIVE_INPUT_PRICE_MULTIPLIER
        + settings.max_output_tokens * output_price
    ) / 1_000_000
    estimated_cost = round(per_attempt * (settings.max_retries + 1), 8)
    ai_usage_accounting.reserve(
        settings,
        identity or UsageIdentity(user_id="internal-match", ip_address="internal-match"),
        estimated_cost,
    )
