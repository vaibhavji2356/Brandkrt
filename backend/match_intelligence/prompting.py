"""Compact prompt construction from the bounded factual context only."""

from dataclasses import dataclass
import json

from research_agent.models import ResearchPackage


SYSTEM_INSTRUCTIONS = """Role: Produce concise creator-match and campaign intelligence.
Goal: Explain practical marketing fit for every supplied profile.
Evidence: Use only FACTUAL_CONTEXT. Never add or infer platform facts, identity, verification, country, website, followers, subscribers, views, engagement, or other metrics. Do not repeat numeric metrics in prose.
Missing evidence: Write exactly "Insufficient verified data." for any fit dimension that lacks support.
Scoring: Do not create overall match scores; the application owns measurable ranking. AI confidence reflects confidence in the qualitative explanation only.
Style: Professional, specific, concise, non-spammy, and non-repetitive.
Output: Return every requested profile_reference exactly once and conform to the JSON schema.
Stop: If evidence cannot support a claim, abstain with the required missing-data sentence."""


@dataclass(frozen=True)
class MatchPrompt:
    context_json: str

    def as_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": f"FACTUAL_CONTEXT\n{self.context_json}"},
        ]


def build_match_prompt(package: ResearchPackage) -> MatchPrompt:
    context = package.ai_context.model_dump(mode="json")
    context["entities"] = [
        item for item in context.get("entities", []) if item.get("entity_type") == "creator"
    ]
    references = {
        f"{item.get('platform')}:{item.get('platform_id')}" for item in context["entities"]
    }
    context["ranking"] = [
        item for item in context.get("ranking", []) if item.get("entity_key") in references
    ]
    return MatchPrompt(json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
