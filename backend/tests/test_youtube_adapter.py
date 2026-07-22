import asyncio
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.source_adapters import YouTubeMockAdapter, build_source_adapters
from brand_discovery_ai.youtube_adapter import YouTubeDataAPIAdapter
from brand_discovery_ai.youtube_config import YouTubeConfigurationError, YouTubeSettings
from brand_discovery_ai.youtube_errors import (
    YouTubeDisabledError, YouTubeInvalidKeyError, YouTubeQuotaError,
    YouTubeResponseError, YouTubeTimeoutError,
)


def run(coro):
    return asyncio.run(coro)


def settings(**updates):
    values = {"api_key": "test-api-key", "timeout_seconds": 2, "max_results": 10, "enabled": True}
    values.update(updates)
    return YouTubeSettings(**values)


def channel(channel_id="UC1234567890123456789012", *, hidden=False):
    return {
        "kind": "youtube#channel", "etag": "raw-etag-must-not-leak", "id": channel_id,
        "snippet": {
            "title": "Engineering Creator", "description": "Robotics and technology videos",
            "customUrl": "@engineeringcreator", "publishedAt": "2020-01-02T03:04:05Z",
            "country": "IN", "thumbnails": {"default": {"url": "https://image.example/raw.jpg"}},
        },
        "statistics": {
            "viewCount": "987654", "subscriberCount": "123000",
            "hiddenSubscriberCount": hidden, "videoCount": "321",
        },
        "brandingSettings": {"channel": {"keywords": 'robotics "machine learning"', "defaultLanguage": "en"}},
        "topicDetails": {"topicCategories": ["https://en.wikipedia.org/wiki/Technology"]},
    }


def success_transport(calls):
    async def handler(request):
        calls.append(request)
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={
                "kind": "youtube#searchListResponse", "etag": "search-raw",
                "items": [{"id": {"kind": "youtube#channel", "channelId": "UC1234567890123456789012"}, "snippet": {"title": "raw"}}],
            })
        if request.url.path.endswith("/channels"):
            return httpx.Response(200, json={"items": [channel()]})
        return httpx.Response(404, json={"error": {}})
    return httpx.MockTransport(handler)


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "configured-key")
    monkeypatch.setenv("YOUTUBE_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("YOUTUBE_MAX_RESULTS", "25")
    monkeypatch.setenv("YOUTUBE_ENABLED", "true")
    configured = YouTubeSettings.from_env()
    assert configured.api_key == "configured-key"
    assert configured.timeout_seconds == 7.5
    assert configured.max_results == 25
    assert configured.enabled is True


@pytest.mark.parametrize("updates", [
    {"enabled": True, "api_key": ""}, {"timeout_seconds": 0.5},
    {"max_results": 0}, {"max_results": 51},
])
def test_invalid_configuration_is_rejected(updates):
    with pytest.raises(YouTubeConfigurationError):
        settings(**updates).validate()


def test_production_factory_replaces_only_youtube_mock():
    adapters = build_source_adapters(youtube_settings=settings())
    assert isinstance(adapters[Platform.YOUTUBE], YouTubeDataAPIAdapter)
    assert not isinstance(adapters[Platform.YOUTUBE], YouTubeMockAdapter)
    assert adapters[Platform.INSTAGRAM].source == "mock:instagram"


def test_creator_search_fetches_details_normalizes_and_never_exposes_raw_response():
    calls = []
    adapter = YouTubeDataAPIAdapter(settings(max_results=8), http_transport=success_transport(calls))
    criteria = DiscoveryCriteria(
        entity_type="creator", platforms=["youtube"], niche="robotics",
        keywords=["technology"], result_limit=3,
    )
    profiles = run(adapter.search_creators(criteria))
    assert len(profiles) == 1 and len(calls) == 2
    profile = profiles[0]
    assert profile.platform_id == "UC1234567890123456789012"
    assert profile.username == "engineeringcreator"
    assert profile.profile_url == "https://www.youtube.com/channel/UC1234567890123456789012"
    assert profile.follower_count == 123000
    assert profile.content_count == 321
    assert profile.total_view_count == 987654
    assert profile.average_views is None
    assert profile.biography == "Robotics and technology videos"
    assert profile.location == "IN" and profile.language == "en"
    assert profile.published_at.isoformat() == "2020-01-02T03:04:05+00:00"
    assert profile.verified is None
    assert profile.source == "youtube_data_api_v3"
    assert "etag" not in profile.model_dump_json() and "thumbnails" not in profile.model_dump_json()
    assert calls[0].url.params["type"] == "channel"
    assert calls[0].url.params["maxResults"] == "3"
    assert calls[0].url.params["key"] == "test-api-key"


def test_repeated_search_uses_memory_cache_and_avoids_quota_calls():
    calls = []
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=success_transport(calls))
    criteria = DiscoveryCriteria(platforms=["youtube"], niche="robotics")
    first = run(adapter.search_creators(criteria))
    second = run(adapter.search_creators(criteria))
    assert first[0].platform_id == second[0].platform_id
    assert len(calls) == 2  # one search.list plus one batched channels.list total


@pytest.mark.parametrize("lookup", [
    "UC1234567890123456789012", "@engineeringcreator", "engineeringcreator",
    "https://www.youtube.com/channel/UC1234567890123456789012",
    "https://youtube.com/@engineeringcreator",
])
def test_profile_lookup_supports_channel_ids_handles_and_urls(lookup):
    calls = []
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=success_transport(calls))
    profile = run(adapter.get_profile(lookup))
    assert profile and profile.platform_id == "UC1234567890123456789012"
    assert calls[0].url.path.endswith("/channels")


def test_profile_lookup_rejects_non_youtube_url_without_request():
    calls = []
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=success_transport(calls))
    assert run(adapter.get_profile("https://evil.example/@name")) is None
    assert calls == []


def test_hidden_subscriber_count_remains_null():
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"items": [channel(hidden=True)]})
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=httpx.MockTransport(handler))
    profile = run(adapter.get_profile("@engineeringcreator"))
    assert profile.follower_count is None
    assert any("hides its subscriber count" in warning for warning in profile.warnings)


@pytest.mark.parametrize("reason,error_type", [
    ("quotaExceeded", YouTubeQuotaError),
    ("dailyLimitExceeded", YouTubeQuotaError),
    ("keyInvalid", YouTubeInvalidKeyError),
    ("accessNotConfigured", YouTubeDisabledError),
])
def test_google_errors_are_mapped_safely(reason, error_type):
    async def handler(request):
        return httpx.Response(403 if reason != "keyInvalid" else 400, json={
            "error": {"code": 403, "message": "private-google-detail", "errors": [{"reason": reason}]}
        })
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(error_type) as caught:
        run(adapter.get_profile("@engineeringcreator"))
    assert "private-google-detail" not in str(caught.value)
    assert "test-api-key" not in str(caught.value)


def test_timeout_is_mapped_safely():
    async def handler(request):
        raise httpx.ReadTimeout("secret upstream detail", request=request)
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(YouTubeTimeoutError) as caught:
        run(adapter.get_profile("@engineeringcreator"))
    assert "secret upstream detail" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_disabled_adapter_never_makes_request():
    calls = []
    adapter = YouTubeDataAPIAdapter(
        settings(enabled=False, api_key=""), http_transport=success_transport(calls),
    )
    assert run(adapter.health_check())["status"] == "disabled"
    with pytest.raises(YouTubeDisabledError):
        run(adapter.get_profile("@engineeringcreator"))
    assert calls == []


def test_invalid_response_is_rejected():
    async def handler(request):
        return httpx.Response(200, json={"items": "not-a-list"})
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(YouTubeResponseError):
        run(adapter.get_profile("@engineeringcreator"))


def test_brand_search_is_not_fabricated():
    adapter = YouTubeDataAPIAdapter(settings(), http_transport=success_transport([]))
    assert adapter.capabilities.brand_discovery is False
    assert run(adapter.search_brands(DiscoveryCriteria(entity_type="brand", platforms=["youtube"]))) == []
