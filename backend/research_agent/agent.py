"""Sequential orchestration from discovery criteria to a fact-only research package."""

from datetime import datetime, timezone
from itertools import combinations

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, EntityType, Platform
from brand_discovery_ai.identity import suggest_identity
from brand_discovery_ai.normalization import deduplicate_profiles
from brand_discovery_ai.ranking import rank_profiles
from brand_discovery_ai.source_adapters import CAPABILITY_REGISTRY

from .context import ContextBuilder
from .dispatcher import ResearchDispatcher, build_mock_dispatcher
from .metrics import research_metrics
from .models import (
    RankingSummaryItem, ResearchPackage, ResearchRun, ResearchTask,
    SourceSummaryItem, TaskPriority, TaskType,
)
from .scheduler import ResearchScheduler
from .validation import TaskValidator


class ResearchAgent:
    def __init__(
        self,
        dispatcher: ResearchDispatcher | None = None,
        *,
        context_token_limit: int = 4000,
    ):
        self.dispatcher = dispatcher or build_mock_dispatcher()
        self.scheduler = ResearchScheduler()
        self.validator = TaskValidator()
        self.context_builder = ContextBuilder(context_token_limit)

    def generate_tasks(self, request: DiscoveryCriteria) -> tuple[list[ResearchTask], list[str]]:
        created_at = datetime.now(timezone.utc)
        query = " ".join(filter(None, [request.niche, *request.categories, *request.keywords])).strip() or "*"
        tasks, warnings = [], []
        entity_types = (
            ["creator", "brand"] if request.entity_type == EntityType.BOTH
            else [request.entity_type.value]
        )
        for platform in request.platforms:
            capabilities = CAPABILITY_REGISTRY[platform]
            for entity_type in entity_types:
                supported = capabilities.creator_discovery if entity_type == "creator" else capabilities.brand_discovery
                if not supported:
                    warnings.append(f"{platform.value} does not support {entity_type} discovery; no task was created.")
                    continue
                tasks.append(ResearchTask(
                    id=f"{platform.value}-{entity_type}-search",
                    type=TaskType.CREATOR_SEARCH if entity_type == "creator" else TaskType.BRAND_SEARCH,
                    priority=TaskPriority.NORMAL,
                    platform=platform.value,
                    entity_type=entity_type,
                    query=query,
                    metadata={"origin": "discovery_request"},
                    created_at=created_at,
                ))
        research_metrics.add("tasks_created", len(tasks))
        return tasks, warnings

    async def research(self, request: DiscoveryCriteria) -> ResearchRun:
        tasks, warnings = self.generate_tasks(request)
        valid = self.validator.validate_all(tasks)
        ordered = self.scheduler.order(valid)
        results = []
        for task in ordered:  # Intentionally sequential in this phase.
            results.append(await self.dispatcher.dispatch(task, request))

        entities = deduplicate_profiles([
            entity for result in results for entity in result.entities
        ])
        ranked = rank_profiles(entities, request)
        ranking_summary = [RankingSummaryItem(
            entity_key=f"{item.profile.platform.value}:{item.profile.platform_id}",
            score=item.score,
            components=item.score_components.model_dump(),
            warnings=item.warnings,
        ) for item in ranked]
        entities = [item.profile for item in ranked]
        identities = []
        for left, right in combinations(entities, 2):
            suggestion = suggest_identity(left, right)
            if suggestion.confidence > 0:
                identities.append(suggestion)
        sources = _source_summary(entities)
        context, context_size = self.context_builder.build(
            request, entities, ranking_summary, sources,
        )
        if context_size.omitted_entities:
            warnings.append(f"{context_size.omitted_entities} entities omitted from AI context to respect the configured limit.")
        missing = _missing_information(entities)
        confidence = round(
            sum(entity.source_confidence for entity in entities) / len(entities), 4
        ) if entities else 0.0
        package = ResearchPackage(
            request_summary=request.model_dump(mode="json", exclude_none=True),
            normalized_entities=entities,
            ranking_summary=ranking_summary,
            identity_suggestions=identities,
            warnings=list(dict.fromkeys(warnings + [warning for result in results for warning in result.warnings])),
            missing_information=missing,
            confidence=confidence,
            source_summary=sources,
            context_size_estimate=context_size,
            ai_context=context,
        )
        return ResearchRun(tasks=ordered, results=results, package=package)


def _source_summary(entities) -> list[SourceSummaryItem]:
    grouped = {}
    for entity in entities:
        grouped.setdefault(entity.source, []).append(entity.source_confidence)
    return [SourceSummaryItem(
        source=source, entity_count=len(values),
        average_confidence=round(sum(values) / len(values), 4),
    ) for source, values in sorted(grouped.items())]


def _missing_information(entities) -> list[str]:
    if not entities:
        return ["No normalized entities were returned."]
    tracked = ("follower_count", "content_count", "engagement_rate", "audience_demographics")
    return [
        f"{field} is unavailable for {sum(getattr(entity, field) is None for entity in entities)} of {len(entities)} entities."
        for field in tracked if any(getattr(entity, field) is None for entity in entities)
    ]
