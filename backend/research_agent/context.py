"""Build compact, bounded, factual context without prompts or internal task data."""

import json
import math
from typing import Any

from .errors import ContextLimitError
from .metrics import research_metrics
from .models import (
    BuiltContext, ContextSizeEstimate, RankingSummaryItem, SourceSummaryItem,
)
from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, NormalizedProfile


FACT_FIELDS = (
    "entity_type", "platform", "platform_id", "username", "display_name",
    "profile_url", "biography", "categories", "keywords", "location", "language",
    "follower_count", "following_count", "content_count", "total_view_count", "average_views",
    "average_likes", "average_comments", "engagement_rate", "verified", "website",
    "business_email_available", "audience_demographics", "source",
    "source_confidence", "published_at", "collected_at", "warnings",
)


class ContextBuilder:
    def __init__(self, token_limit: int = 4000):
        if token_limit < 64:
            raise ValueError("context token limit must be at least 64")
        self.token_limit = token_limit

    def build(
        self,
        criteria: DiscoveryCriteria,
        entities: list[NormalizedProfile],
        ranking: list[RankingSummaryItem],
        sources: list[SourceSummaryItem],
    ) -> tuple[BuiltContext, ContextSizeEstimate]:
        request = criteria.model_dump(mode="json", exclude_none=True)
        base = BuiltContext(
            request=request,
            entities=[],
            ranking=[],
            sources=[item.model_dump(mode="json") for item in sources],
        )
        if estimate_tokens(base.model_dump(mode="json")) > self.token_limit:
            raise ContextLimitError("Context limit is too small for the request summary.")

        rank_by_key = {item.entity_key: item for item in ranking}
        omitted = 0
        for entity in entities:
            fact = _compact_entity(entity)
            key = f"{entity.platform.value}:{entity.platform_id}"
            rank = rank_by_key.get(key)
            candidate = base.model_copy(deep=True)
            candidate.entities.append(fact)
            if rank:
                candidate.ranking.append(rank.model_dump(mode="json"))
            if estimate_tokens(candidate.model_dump(mode="json")) <= self.token_limit:
                base = candidate
            else:
                omitted += 1

        serialized = _serialized(base.model_dump(mode="json"))
        estimate = ContextSizeEstimate(
            characters=len(serialized), estimated_tokens=estimate_tokens(base.model_dump(mode="json")),
            included_entities=len(base.entities), omitted_entities=omitted,
            token_limit=self.token_limit,
        )
        research_metrics.set_gauge("context_size", estimate.characters)
        research_metrics.set_gauge("estimated_tokens", estimate.estimated_tokens)
        return base, estimate


def estimate_tokens(value: Any) -> int:
    """Conservative deterministic estimate; no tokenizer or model dependency."""
    return math.ceil(len(_serialized(value).encode("utf-8")) / 4)


def _serialized(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compact_entity(entity: NormalizedProfile) -> dict[str, Any]:
    raw = entity.model_dump(mode="json")
    return {field: raw[field] for field in FACT_FIELDS if raw.get(field) not in (None, [], {})}
