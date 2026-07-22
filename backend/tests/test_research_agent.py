import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.ranking import rank_profiles
from brand_discovery_ai.source_adapters import build_mock_adapters
from research_agent.agent import ResearchAgent
from research_agent.context import ContextBuilder, estimate_tokens
from research_agent.dispatcher import build_mock_dispatcher
from research_agent.errors import ContextLimitError, TaskValidationError, UnsupportedTaskError
from research_agent.metrics import research_metrics
from research_agent.models import (
    RankingSummaryItem, ResearchTask, SourceSummaryItem, TaskPriority,
    TaskStatus, TaskType,
)
from research_agent.scheduler import ResearchScheduler
from research_agent.validation import TaskValidator


def run(coro):
    return asyncio.run(coro)


def task(task_type=TaskType.CREATOR_SEARCH, **updates):
    values = {
        "id": "task-1", "type": task_type, "priority": TaskPriority.NORMAL,
        "platform": "instagram", "entity_type": "creator", "query": "fitness",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    values.update(updates)
    return ResearchTask(**values)


def test_scheduler_priority_order_is_deterministic():
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tasks = [
        task(id="low", priority="LOW", created_at=created),
        task(id="normal-later", priority="NORMAL", created_at=created + timedelta(seconds=1)),
        task(id="high-b", priority="HIGH", created_at=created),
        task(id="high-a", priority="HIGH", created_at=created),
        task(id="normal-first", priority="NORMAL", created_at=created),
    ]
    ordered = ResearchScheduler().order(tasks)
    assert [item.id for item in ordered] == ["high-a", "high-b", "normal-first", "normal-later", "low"]


@pytest.mark.parametrize("task_type", list(TaskType))
def test_task_schema_supports_every_declared_type(task_type):
    kwargs = {"platform": None} if task_type in {TaskType.WEBSITE_LOOKUP, TaskType.FUTURE_CUSTOM_TASK} else {}
    assert task(task_type, **kwargs).type == task_type


@pytest.mark.parametrize("invalid", [
    task(id="bad-platform", platform="myspace"),
    task(id="unsafe-scheme", query="javascript:alert(1)"),
    task(id="secret-shaped", query="api_key=do-not-log"),
    task(TaskType.KEYWORD_LOOKUP, id="unsupported", platform="snapchat"),
    task(TaskType.WEBSITE_LOOKUP, id="network", platform="website", entity_type=None, query="https://example.com"),
])
def test_validator_rejects_invalid_or_unsupported_tasks(invalid):
    with pytest.raises(TaskValidationError):
        TaskValidator().validate_all([invalid])


def test_validator_rejects_empty_and_duplicate_tasks():
    empty = task().model_copy(update={"query": ""})
    with pytest.raises(TaskValidationError, match="empty"):
        TaskValidator().validate_all([empty])
    duplicate = task(id="task-2", query=" FITNESS ")
    with pytest.raises(TaskValidationError, match="Duplicate"):
        TaskValidator().validate_all([task(), duplicate])


def test_mock_dispatcher_executes_without_provider_internals_or_network():
    research_task = task()
    criteria = DiscoveryCriteria(entity_type="creator", platforms=["instagram"], niche="fitness")
    result = run(build_mock_dispatcher().dispatch(research_task, criteria))
    assert result.status == TaskStatus.COMPLETED
    assert research_task.status == TaskStatus.COMPLETED
    assert result.entities and all(item.source == "mock:instagram" for item in result.entities)


def test_dispatcher_rejects_task_without_implementation():
    custom = task(TaskType.FUTURE_CUSTOM_TASK, platform=None)
    with pytest.raises(UnsupportedTaskError):
        run(build_mock_dispatcher().dispatch(custom, DiscoveryCriteria(platforms=["instagram"])))


def context_inputs():
    criteria = DiscoveryCriteria(entity_type="creator", platforms=["instagram"], niche="fitness")
    entities = run(build_mock_adapters()[Platform.INSTAGRAM].search_creators(criteria))
    ranked = rank_profiles(entities, criteria)
    summary = [RankingSummaryItem(
        entity_key=f"{item.profile.platform.value}:{item.profile.platform_id}",
        score=item.score, components=item.score_components.model_dump(), warnings=item.warnings,
    ) for item in ranked]
    sources = [SourceSummaryItem(source="mock:instagram", entity_count=len(entities), average_confidence=0.82)]
    return criteria, entities, summary, sources


def test_context_builder_removes_internal_metadata_and_duplicates_upstream():
    criteria, entities, ranking, sources = context_inputs()
    context, size = ContextBuilder(4000).build(criteria, entities, ranking, sources)
    serialized = context.model_dump_json()
    assert size.included_entities == len(entities)
    assert '"metadata"' not in serialized and '"priority"' not in serialized
    assert '"task_id"' not in serialized and "business_email_hash" not in serialized
    assert all("follower_count" in item for item in context.entities)


def test_token_estimation_is_deterministic_and_utf8_aware():
    value = {"fact": "creator metrics café", "count": 1200}
    assert estimate_tokens(value) == estimate_tokens(value)
    assert estimate_tokens(value) > 0
    assert estimate_tokens({"fact": "x" * 100}) > estimate_tokens({"fact": "x"})


def test_oversized_entity_context_is_bounded_with_omission():
    criteria, entities, ranking, sources = context_inputs()
    context, size = ContextBuilder(220).build(criteria, entities, ranking, sources)
    assert size.estimated_tokens <= 220
    assert size.omitted_entities > 0
    assert size.included_entities == len(context.entities)


def test_oversized_request_envelope_fails_safely():
    criteria = DiscoveryCriteria(platforms=["instagram"], campaign_objective="x" * 500)
    with pytest.raises(ContextLimitError):
        ContextBuilder(64).build(criteria, [], [], [])


def test_research_agent_returns_complete_fact_only_package_and_metrics():
    research_metrics.reset()
    criteria = DiscoveryCriteria(
        entity_type="both", platforms=["instagram", "snapchat"],
        niche="fitness", minimum_followers=1000, result_limit=10,
    )
    run_result = run(ResearchAgent(context_token_limit=2500).research(criteria))
    package = run_result.package
    assert run_result.tasks
    assert all(item.status == TaskStatus.COMPLETED for item in run_result.tasks)
    assert package.normalized_entities
    assert package.ranking_summary
    assert package.source_summary
    assert package.context_size_estimate.estimated_tokens <= 2500
    assert package.confidence == pytest.approx(0.82)
    assert any("snapchat does not support brand" in warning for warning in package.warnings)
    assert any("follower_count" in item for item in package.missing_information)
    metrics = research_metrics.snapshot()
    assert metrics["tasks_created"] == len(run_result.tasks)
    assert metrics["tasks_completed"] == len(run_result.tasks)
    assert metrics["context_size"] == package.context_size_estimate.characters
    assert metrics["estimated_tokens"] == package.context_size_estimate.estimated_tokens


def test_agent_deduplicates_provider_results_before_packaging():
    criteria = DiscoveryCriteria(entity_type="creator", platforms=["instagram"])
    first = run(ResearchAgent().research(criteria))
    keys = [(item.platform, item.platform_id) for item in first.package.normalized_entities]
    assert len(keys) == len(set(keys))
