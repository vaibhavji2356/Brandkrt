import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import (
    AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform,
)
from brand_discovery_ai.source_adapters import SourceProvider
from research_agent.agent import ResearchAgent
from research_agent.dispatcher import ResearchDispatcher
from research_agent.models import ResearchTask, TaskStatus, TaskType
from research_agent.provider_orchestrator import ProviderOrchestrator


def run(coro):
    return asyncio.run(coro)


def profile(
    platform: Platform, profile_id: str, *, username: str | None = None,
    source_confidence: float = 0.9, complete: bool = True,
) -> NormalizedProfile:
    username = username or f"creator_{profile_id}"
    return NormalizedProfile(
        entity_type="creator", platform=platform, platform_id=profile_id,
        username=username, display_name=f"Creator {profile_id}" if complete else None,
        profile_url=f"https://{platform.value}.example.com/{username}",
        biography="Technology creator" if complete else None,
        categories=["technology"], keywords=["software"],
        location="Mumbai" if complete else None, language=None,
        follower_count=12000 if complete else None, following_count=None,
        content_count=250 if complete else None, total_view_count=None,
        average_views=None, average_likes=None, average_comments=None,
        engagement_rate=None, verified=True if complete else None,
        website=None, business_email_available=None, business_email_hash=None,
        linked_social_urls=[], audience_demographics=None,
        source=f"test:{platform.value}", source_confidence=source_confidence,
        published_at=None, collected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        warnings=[],
    )


def capabilities(**updates):
    values = {
        "keyword_search": True, "category_search": False,
        "username_lookup": True, "location_filtering": False,
        "follower_metrics": True, "content_metrics": True,
        "audience_demographics": False, "brand_discovery": False,
        "creator_discovery": True,
    }
    values.update(updates)
    return AdapterCapabilities(**values)


class StubProvider(SourceProvider):
    def __init__(
        self, platform: Platform, entities=None, *, health_status="ok",
        delay=0, failure=None, provider_capabilities=None,
    ):
        self.platform = platform
        self.entities = entities or []
        self.health_status = health_status
        self.delay = delay
        self.failure = failure
        self._capabilities = provider_capabilities or capabilities()
        self.health_calls = 0
        self.execution_calls = 0

    @property
    def capabilities(self):
        return self._capabilities

    async def health_check(self):
        self.health_calls += 1
        return {"status": self.health_status, "private": "must-not-leak"}

    async def _result(self):
        self.execution_calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.failure:
            raise self.failure
        return list(self.entities)

    async def search_creators(self, criteria):
        del criteria
        return await self._result()

    async def search_brands(self, criteria):
        del criteria
        return await self._result()

    async def get_profile(self, platform_id_or_username):
        del platform_id_or_username
        results = await self._result()
        return results[0] if results else None


def task(platform: Platform, *, task_id=None, task_type=TaskType.CREATOR_SEARCH):
    return ResearchTask(
        id=task_id or f"{platform.value}-{task_type.value}",
        type=task_type, platform=platform.value, entity_type="creator",
        query="software", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def criteria(*platforms):
    return DiscoveryCriteria(
        entity_type="creator", platforms=[item.value for item in platforms],
        niche="software", result_limit=10,
    )


def test_single_provider_execution_and_attribution():
    youtube = StubProvider(Platform.YOUTUBE, [profile(Platform.YOUTUBE, "yt-1")])
    result = run(ProviderOrchestrator([youtube]).execute(
        [task(Platform.YOUTUBE)], criteria(Platform.YOUTUBE),
    ))

    assert result.providers_used == ["youtube"]
    assert result.providers_failed == [] and result.providers_skipped == []
    assert len(result.aggregated_results) == 1
    attributed = result.aggregated_results[0]
    assert attributed.provider == "youtube"
    assert attributed.platform == Platform.YOUTUBE
    assert attributed.source == "test:youtube"
    assert attributed.source_confidence == 0.9
    assert result.task_results[0].status == TaskStatus.COMPLETED


def test_multiple_provider_concurrent_execution_preserves_input_order():
    youtube = StubProvider(
        Platform.YOUTUBE, [profile(Platform.YOUTUBE, "yt-1")], delay=0.02,
    )
    twitch = StubProvider(
        Platform.TWITCH, [profile(Platform.TWITCH, "tw-1")], delay=0.001,
    )
    orchestrator = ProviderOrchestrator([twitch, youtube], concurrent=True)
    result = run(orchestrator.execute(
        [task(Platform.YOUTUBE), task(Platform.TWITCH)],
        criteria(Platform.YOUTUBE, Platform.TWITCH),
    ))

    assert result.providers_used == ["youtube", "twitch"]
    assert [item.platform for item in result.aggregated_results] == [
        Platform.YOUTUBE, Platform.TWITCH,
    ]


def test_disabled_and_unhealthy_providers_are_skipped_without_execution():
    disabled = StubProvider(Platform.X, health_status="disabled")
    unhealthy = StubProvider(Platform.TWITCH, health_status="degraded")
    result = run(ProviderOrchestrator([disabled, unhealthy]).execute(
        [task(Platform.X), task(Platform.TWITCH)], criteria(Platform.X, Platform.TWITCH),
    ))

    assert result.providers_skipped == ["x", "twitch"]
    assert disabled.execution_calls == unhealthy.execution_calls == 0
    assert all(item.status == TaskStatus.REJECTED for item in result.task_results)
    assert any("disabled" in warning for warning in result.warnings)
    assert any("unhealthy" in warning for warning in result.warnings)
    assert "must-not-leak" not in result.model_dump_json()


def test_provider_timeout_cancels_only_that_provider_and_returns_partial_success():
    slow = StubProvider(
        Platform.YOUTUBE, [profile(Platform.YOUTUBE, "slow")], delay=0.05,
    )
    twitch = StubProvider(Platform.TWITCH, [profile(Platform.TWITCH, "tw-1")])
    orchestrator = ProviderOrchestrator(
        [slow, twitch], concurrent=True,
        provider_timeouts={Platform.YOUTUBE: 0.01, Platform.TWITCH: 0.1},
    )
    result = run(orchestrator.execute(
        [task(Platform.YOUTUBE), task(Platform.TWITCH)],
        criteria(Platform.YOUTUBE, Platform.TWITCH),
    ))

    assert result.providers_failed == ["youtube"]
    assert result.providers_used == ["twitch"]
    assert [item.platform for item in result.aggregated_results] == [Platform.TWITCH]
    assert any("timed out" in warning for warning in result.warnings)


def test_provider_failure_is_safe_and_does_not_hide_other_results():
    failed = StubProvider(
        Platform.X, failure=RuntimeError("raw token and upstream response"),
    )
    youtube = StubProvider(Platform.YOUTUBE, [profile(Platform.YOUTUBE, "yt-1")])
    result = run(ProviderOrchestrator([failed, youtube]).execute(
        [task(Platform.X), task(Platform.YOUTUBE)],
        criteria(Platform.X, Platform.YOUTUBE),
    ))

    serialized = result.model_dump_json()
    assert result.providers_failed == ["x"] and result.providers_used == ["youtube"]
    assert "raw token" not in serialized and "upstream response" not in serialized
    assert any("failed safely" in warning for warning in result.warnings)


def test_malformed_provider_output_isolated_as_failure():
    malformed = StubProvider(Platform.X, entities=[{"raw": "payload"}])
    result = run(ProviderOrchestrator([malformed]).execute(
        [task(Platform.X)], criteria(Platform.X),
    ))
    assert result.providers_failed == ["x"]
    assert result.aggregated_results == []
    assert result.task_results[0].status == TaskStatus.FAILED
    assert any("malformed normalized data" in warning for warning in result.warnings)


def test_duplicate_detection_uses_same_platform_id_username_and_url_only():
    first = profile(Platform.YOUTUBE, "id-1", username="same", source_confidence=0.8)
    stronger = profile(Platform.YOUTUBE, "id-2", username="same", source_confidence=0.95)
    cross_platform = profile(Platform.TWITCH, "id-1", username="same", source_confidence=0.9)
    youtube = StubProvider(Platform.YOUTUBE, [first, stronger])
    twitch = StubProvider(Platform.TWITCH, [cross_platform])
    result = run(ProviderOrchestrator([youtube, twitch]).execute(
        [task(Platform.YOUTUBE), task(Platform.TWITCH)],
        criteria(Platform.YOUTUBE, Platform.TWITCH),
    ))

    assert len(result.aggregated_results) == 2
    youtube_result = next(item for item in result.aggregated_results if item.platform == Platform.YOUTUBE)
    assert youtube_result.entity.platform_id == "id-2"
    assert any(item.platform == Platform.TWITCH for item in result.aggregated_results)


def test_confidence_is_conservative_for_discovery_and_missing_data():
    complete = profile(Platform.YOUTUBE, "complete", source_confidence=0.9)
    incomplete = profile(Platform.YOUTUBE, "incomplete", source_confidence=0.9, complete=False)
    provider = StubProvider(Platform.YOUTUBE, [complete])
    exact = run(ProviderOrchestrator([provider]).execute(
        [task(Platform.YOUTUBE, task_type=TaskType.PROFILE_LOOKUP)],
        criteria(Platform.YOUTUBE),
    ))
    provider = StubProvider(Platform.YOUTUBE, [complete, incomplete])
    discovery = run(ProviderOrchestrator([provider]).execute(
        [task(Platform.YOUTUBE)], criteria(Platform.YOUTUBE),
    ))

    assert exact.aggregate_confidence == 0.9
    assert discovery.aggregate_confidence < exact.aggregate_confidence
    assert discovery.aggregate_confidence <= 0.9
    complete_score, incomplete_score = [
        item.adjusted_confidence for item in discovery.aggregated_results
    ]
    assert incomplete_score < complete_score


def test_unsupported_capability_is_skipped_with_warning():
    youtube = StubProvider(
        Platform.YOUTUBE, provider_capabilities=capabilities(brand_discovery=False),
    )
    brand_task = task(Platform.YOUTUBE, task_type=TaskType.BRAND_SEARCH)
    brand_task.entity_type = "brand"
    result = run(ProviderOrchestrator([youtube]).execute(
        [brand_task], DiscoveryCriteria(entity_type="brand", platforms=["youtube"]),
    ))
    assert result.providers_skipped == ["youtube"]
    assert result.task_results[0].status == TaskStatus.REJECTED
    assert any("does not support" in warning for warning in result.warnings)


def test_research_agent_uses_orchestrator_without_public_package_changes():
    youtube = StubProvider(Platform.YOUTUBE, [profile(Platform.YOUTUBE, "yt-1")])
    twitch = StubProvider(Platform.TWITCH, [profile(Platform.TWITCH, "tw-1")])
    dispatcher = ResearchDispatcher(
        orchestrator=ProviderOrchestrator([youtube, twitch], concurrent=True),
    )
    result = run(ResearchAgent(dispatcher=dispatcher).research(
        criteria(Platform.YOUTUBE, Platform.TWITCH),
    ))

    assert all(item.status == TaskStatus.COMPLETED for item in result.results)
    assert {item.platform for item in result.package.normalized_entities} == {
        Platform.YOUTUBE, Platform.TWITCH,
    }
    assert result.package.confidence > 0
    assert "providers_used" not in result.package.model_dump()
