"""Bounded factual context for optional Creator Intelligence narration."""

from dataclasses import dataclass
import json

from .models import CreatorIntelligenceRequest, CreatorIntelligenceResponse


SYSTEM_INSTRUCTIONS = """Role: Explain the supplied deterministic creator-intelligence result.
Authority: DETERMINISTIC_RESULT is the only source of truth. Never alter ranking, selection, scores, rates, currency, budget, spend, confidence, reach, engagements, or ROI.
Evidence: Do not add creator identities, audience attributes, demographics, metrics, outcomes, or external validation. Followers are not reach. Estimates are not verified facts.
Safety: Do not promise or guarantee reach, engagement, installs, conversions, sales, or revenue. Use plain text only; do not emit markdown or HTML.
Numbers: Avoid numeric claims. If essential, copy the exact value from DETERMINISTIC_RESULT without conversion or rounding changes.
Completeness: Return creator_narratives in exactly the same order as ranking, including every ranked creator exactly once.
Output: Conform exactly to the provided JSON schema. Unknown fields are forbidden."""


@dataclass(frozen=True)
class NarrativePrompt:
    context_json: str

    def as_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": f"DETERMINISTIC_RESULT\n{self.context_json}"},
        ]


def build_narrative_prompt(request: CreatorIntelligenceRequest, result: CreatorIntelligenceResponse) -> NarrativePrompt:
    factual_result = result.model_dump(
        mode="json",
        exclude={"ai_narrative", "narrative_source", "narrative_degraded"},
    )
    context = {
        "campaign_objective": request.campaign_objective.value,
        "deterministic_result": factual_result,
    }
    return NarrativePrompt(json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
