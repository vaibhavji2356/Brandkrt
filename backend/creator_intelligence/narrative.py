"""Optional grounded narrative orchestration with deterministic degradation."""

import json

from brand_discovery_ai.costing import CONSERVATIVE_INPUT_PRICE_MULTIPLIER, MODEL_PRICING_USD_PER_MTOK, estimate_text_tokens
from brand_discovery_ai.usage import UsageIdentity, ai_usage_accounting

from .models import (
    CreatorIntelligenceRequest, CreatorIntelligenceResponse, CreatorNarrative,
    PortfolioNarrative,
)
from .narrative_grounding import validate_narrative
from .narrative_prompting import build_narrative_prompt
from .narrative_provider import CreatorNarrativeProvider, OpenAICreatorNarrativeProvider, provider_narrative_schema


_MAX_NARRATIVE_INPUT_TOKENS = 20_000


class CreatorNarrativeService:
    def __init__(self, provider: CreatorNarrativeProvider | None = None):
        self.provider = provider

    async def enrich(self, request: CreatorIntelligenceRequest, result: CreatorIntelligenceResponse,
                     usage_identity: UsageIdentity | None = None) -> CreatorIntelligenceResponse:
        if not request.include_ai_narrative:
            return result
        fallback = deterministic_fallback_narrative(request, result)
        if self.provider is None:
            return _fallback(result, fallback, "AI narrative is unavailable; deterministic narrative returned.")
        try:
            prompt = build_narrative_prompt(request, result)
            _reserve_if_paid(self.provider, prompt, usage_identity)
            raw = await self.provider.narrate(prompt)
            narrative = PortfolioNarrative.model_validate(raw)
            validate_narrative(narrative, result)
            return result.model_copy(update={
                "ai_narrative": narrative, "narrative_source": "openai_grounded",
                "narrative_degraded": False,
            })
        except Exception:
            return _fallback(
                result, fallback,
                "AI narrative failed validation or was unavailable; deterministic narrative returned.",
            )


def deterministic_fallback_narrative(request: CreatorIntelligenceRequest,
                                     result: CreatorIntelligenceResponse) -> PortfolioNarrative:
    selected = [item for item in result.recommendations if item.selected]
    creators = []
    for item in result.recommendations:
        creators.append(CreatorNarrative(
            profile_reference=item.profile_reference, platform=item.platform,
            platform_id=item.profile_reference.split(":", 1)[1], username=item.username,
            selection_reason=(
                "Selected by the deterministic budget portfolio." if item.selected
                else "Ranked by deterministic fit but not selected for the current portfolio."
            ),
            strengths=item.explanation.strengths[:5], weaknesses=item.explanation.weaknesses[:5],
            pricing_assessment=item.explanation.pricing_concerns[0],
            negotiation_guidance="Confirm the rate, deliverables, usage rights, and evidence before agreement.",
            uncertainty="Confidence is limited to the factual and supplied measurements currently available.",
            risk_flags=(item.explanation.risks or ["Campaign outcomes remain uncertain."])[:5],
        ))
    major_warnings = [_bounded(warning) for warning in result.warnings[:5]] or ["No additional deterministic warnings were reported."]
    selected_names = _bounded(
        ", ".join(item.username or item.profile_reference for item in selected[:3]) or "no funded creators",
        limit=300,
    )
    return PortfolioNarrative(
        executive_summary=f"The deterministic portfolio selected {selected_names} for the supplied campaign objective.",
        objective_alignment=f"Recommendations were evaluated for {request.campaign_objective.value} using measurable available data.",
        budget_assessment=(
            f"Expected spend is {result.budget_analysis.expected_spend:.2f} {request.currency} from a "
            f"{result.budget_analysis.campaign_budget:.2f} {request.currency} budget, with "
            f"{result.budget_analysis.budget_utilization:.2f}% utilization."
        ),
        portfolio_tradeoffs=[
            "Selection balances deterministic fit and affordability within the requested creator count.",
            "Unpriced or over-budget creators can remain ranked without entering the funded portfolio.",
        ],
        expected_efficiency_summary="Efficiency values are planning estimates based only on available rates and observed metrics.",
        risk_summary=major_warnings,
        recommended_actions=[
            "Verify commercial terms and evidence before contracting.",
            "Capture observed campaign performance for later estimate-versus-actual comparison.",
        ],
        creator_narratives=creators,
        confidence_statement=f"Portfolio confidence is {result.confidence:.4f} and declines when evidence is missing or unverified.",
        warnings=major_warnings,
    )


def _fallback(result: CreatorIntelligenceResponse, narrative: PortfolioNarrative,
              warning: str) -> CreatorIntelligenceResponse:
    return result.model_copy(update={
        "ai_narrative": narrative, "narrative_source": "deterministic_fallback",
        "narrative_degraded": True,
        "warnings": list(dict.fromkeys([*result.warnings, warning])),
    })


def _bounded(value: str, limit: int = 500) -> str:
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned:
        return "Insufficient verified data."
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _reserve_if_paid(provider: CreatorNarrativeProvider, prompt, identity: UsageIdentity | None) -> None:
    serialized_prompt = json.dumps(prompt.as_messages(), ensure_ascii=False, separators=(",", ":"))
    schema_json = json.dumps(provider_narrative_schema(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    input_tokens = estimate_text_tokens(serialized_prompt) + estimate_text_tokens(schema_json)
    if input_tokens > _MAX_NARRATIVE_INPUT_TOKENS:
        raise ValueError("Narrative input exceeds the configured context limit.")
    if not isinstance(provider, OpenAICreatorNarrativeProvider):
        return
    settings = provider.settings
    prices = MODEL_PRICING_USD_PER_MTOK.get(settings.model)
    if prices is None:
        raise ValueError("Model pricing is unavailable.")
    input_price, output_price = prices
    estimated_cost = round((
        input_tokens * input_price * CONSERVATIVE_INPUT_PRICE_MULTIPLIER
        + settings.max_output_tokens * output_price
    ) / 1_000_000, 8)
    ai_usage_accounting.reserve(
        settings,
        identity or UsageIdentity(user_id="internal-creator-narrative", ip_address="internal-creator-narrative"),
        estimated_cost,
    )
