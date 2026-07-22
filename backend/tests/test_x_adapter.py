import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.source_adapters import XMockAdapter, build_mock_adapters, build_source_adapters
from brand_discovery_ai.twitch_config import TwitchSettings
from brand_discovery_ai.x_adapter import XApiAdapter
from brand_discovery_ai.x_config import XConfigurationError, XSettings
from brand_discovery_ai.x_errors import (
    XAccessRestrictedError, XDisabledError, XInvalidTokenError,
    XMalformedRequestError, XRateLimitError, XResponseError, XTimeoutError,
    XUnavailableError, XUnsupportedCapabilityError,
)
from brand_discovery_ai.youtube_config import YouTubeSettings
from research_agent.dispatcher import MockPlatformExecutionProvider, ResearchDispatcher
from research_agent.models import ResearchTask, TaskType


def run(coro):
    return asyncio.run(coro)


def settings(**updates):
    values = {
        "enabled": True, "bearer_token": "test-bearer-token",
        "timeout_seconds": 2, "max_results": 10, "cache_ttl_seconds": 300,
    }
    values.update(updates)
    return XSettings(**values)


def user(user_id="2244994945", username="XDevelopers"):
    return {
        "id": user_id, "name": "X Developers", "username": username,
        "created_at": "2013-12-14T04:35:55.000Z",
        "description": "The voice of the X developer community.",
        "location": "San Francisco, CA", "verified": True, "verified_type": "blue",
        "protected": False, "profile_image_url": "https://pbs.twimg.com/profile_images/test.jpg",
        "url": "https://t.co/redirect",
        "entities": {"url": {"urls": [{
            "url": "https://t.co/redirect", "expanded_url": "https://developer.x.com/",
        }]}},
        "public_metrics": {
            "followers_count": 583423, "following_count": 2048,
            "tweet_count": 14052, "listed_count": 1672,
        },
    }


def success_transport(calls, *, search_data=None, profile_data=None):
    search_data = [user()] if search_data is None else search_data
    profile_data = user() if profile_data is None else profile_data

    async def handler(request):
        calls.append(request)
        if request.url.path.endswith("/users/search"):
            return httpx.Response(200, json={"data": search_data, "meta": {"result_count": len(search_data)}})
        return httpx.Response(200, json={"data": profile_data})

    return httpx.MockTransport(handler)


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("X_ENABLED", "true")
    monkeypatch.setenv("X_BEARER_TOKEN", "configured-token")
    monkeypatch.setenv("X_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("X_MAX_RESULTS", "25")
    monkeypatch.setenv("X_CACHE_TTL_SECONDS", "120")
    configured = XSettings.from_env()
    assert configured.enabled is True and configured.timeout_seconds == 7.5
    assert configured.max_results == 25 and configured.cache_ttl_seconds == 120
    assert "configured-token" not in repr(configured)


@pytest.mark.parametrize("updates", [
    {"bearer_token": ""}, {"timeout_seconds": 0}, {"max_results": 0},
    {"max_results": 51}, {"cache_ttl_seconds": 0},
])
def test_invalid_configuration_is_rejected_without_credentials(updates):
    with pytest.raises(XConfigurationError) as caught:
        settings(**updates).validate()
    assert "test-bearer-token" not in str(caught.value)


def test_disabled_configuration_is_safe_and_network_free():
    calls = []
    adapter = XApiAdapter(
        settings(enabled=False, bearer_token=""), http_transport=success_transport(calls),
    )
    assert run(adapter.health_check()) == {"status": "disabled", "platform": "x", "network": False}
    assert not adapter.capabilities.creator_discovery
    with pytest.raises(XDisabledError):
        run(adapter.get_profile("XDevelopers"))
    assert calls == []


def test_production_factory_replaces_only_x_while_mock_factory_stays_mock():
    adapters = build_source_adapters(
        youtube_settings=YouTubeSettings(enabled=False),
        twitch_settings=TwitchSettings(enabled=False), x_settings=settings(),
    )
    assert isinstance(adapters[Platform.X], XApiAdapter)
    assert not isinstance(adapters[Platform.X], XMockAdapter)
    mocks = build_mock_adapters()
    assert isinstance(mocks[Platform.X], XMockAdapter)
    assert run(mocks[Platform.X].health_check())["network"] is False


def test_exact_username_and_id_lookup_normalize_official_facts_only():
    for lookup, expected_path in (
        ("@XDevelopers", "/2/users/by/username/xdevelopers"),
        ("2244994945", "/2/users/2244994945"),
        ("https://x.com/XDevelopers", "/2/users/by/username/xdevelopers"),
    ):
        calls = []
        adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
        profile = run(adapter.get_profile(lookup))
        assert profile and calls[0].url.path == expected_path
        assert profile.platform == Platform.X and profile.platform_id == "2244994945"
        assert profile.username == "XDevelopers" and profile.display_name == "X Developers"
        assert profile.profile_url == "https://x.com/XDevelopers"
        assert profile.location == "San Francisco, CA"
        assert profile.website == "https://developer.x.com/"
        assert profile.follower_count == 583423 and profile.following_count == 2048
        assert profile.content_count == 14052 and profile.verified is True
        assert profile.published_at.isoformat() == "2013-12-14T04:35:55+00:00"
        assert profile.source == "x_api_v2" and profile.source_confidence == 0.98
        assert profile.engagement_rate is None and profile.language is None
        assert profile.audience_demographics is None and profile.business_email_available is None
        serialized = profile.model_dump_json()
        assert "profile_image_url" not in serialized
        assert "listed_count" not in serialized and "verified_type" not in serialized


def test_bounded_creator_search_and_empty_search():
    calls = []
    adapter = XApiAdapter(
        settings(max_results=8), http_transport=success_transport(calls, search_data=[user(), user("12", "Second")]),
    )
    profiles = run(adapter.search_creators(DiscoveryCriteria(
        platforms=["x"], niche="software", keywords=["developer"], result_limit=3,
    )))
    assert len(profiles) == 2
    assert calls[0].url.params["query"] == "software developer"
    assert calls[0].url.params["max_results"] == "3"
    empty = XApiAdapter(settings(), http_transport=success_transport([], search_data=[]))
    assert run(empty.search_creators(DiscoveryCriteria(platforms=["x"], niche="missing"))) == []


def test_exact_creator_search_uses_lookup_not_broad_search():
    calls = []
    adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
    profiles = run(adapter.search_creators(DiscoveryCriteria(platforms=["x"], keywords=["@XDevelopers"])))
    assert len(profiles) == 1
    assert calls[0].url.path == "/2/users/by/username/xdevelopers"


def test_category_only_search_is_explicitly_unsupported_and_brands_are_conservative():
    calls = []
    adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
    with pytest.raises(XUnsupportedCapabilityError):
        run(adapter.search_creators(DiscoveryCriteria(platforms=["x"], categories=["technology"])))
    assert run(adapter.search_brands(DiscoveryCriteria(platforms=["x"], niche="technology"))) == []
    assert adapter.capabilities.category_search is False
    assert adapter.capabilities.brand_discovery is False
    assert calls == []


def test_unsafe_or_unsupported_search_query_is_rejected_before_network():
    calls = []
    adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
    with pytest.raises(XMalformedRequestError):
        run(adapter.search_creators(DiscoveryCriteria(platforms=["x"], niche="software OR -is:retweet")))
    assert calls == []


@pytest.mark.parametrize("status,error_type", [
    (400, XMalformedRequestError), (401, XInvalidTokenError),
    (403, XAccessRestrictedError), (429, XRateLimitError),
])
def test_provider_errors_are_safe_and_not_cached(status, error_type):
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"detail": "raw upstream secret detail"})
    adapter = XApiAdapter(settings(), http_transport=httpx.MockTransport(handler))
    for _ in range(2):
        with pytest.raises(error_type) as caught:
            run(adapter.get_profile("XDevelopers"))
        message = str(caught.value)
        assert "test-bearer-token" not in message and "raw upstream" not in message
    assert len(calls) == 2


def test_missing_profile_is_none_and_404_is_not_cached():
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(404, json={"detail": "missing"})
    adapter = XApiAdapter(settings(), http_transport=httpx.MockTransport(handler))
    assert run(adapter.get_profile("XDevelopers")) is None
    assert run(adapter.get_profile("XDevelopers")) is None
    assert len(calls) == 2


def test_timeout_and_malformed_json_are_safe():
    async def timeout_handler(request):
        raise httpx.ReadTimeout("private URL and token detail", request=request)
    adapter = XApiAdapter(settings(), http_transport=httpx.MockTransport(timeout_handler))
    with pytest.raises(XTimeoutError) as caught:
        run(adapter.get_profile("XDevelopers"))
    assert "private" not in str(caught.value) and caught.value.__cause__ is None

    malformed = XApiAdapter(
        settings(), http_transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"not-json")),
    )
    with pytest.raises(XResponseError):
        run(malformed.get_profile("XDevelopers"))


def test_server_failure_gets_one_retry_then_safe_failure():
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(503, json={"detail": "internal topology"})
    adapter = XApiAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(XUnavailableError) as caught:
        run(adapter.get_profile("XDevelopers"))
    assert len(calls) == 2 and "topology" not in str(caught.value)


def test_success_cache_hit_expiry_and_separate_search_key(monkeypatch):
    calls = []
    now = [100.0]
    monkeypatch.setattr("brand_discovery_ai.x_adapter.time.monotonic", lambda: now[0])
    adapter = XApiAdapter(settings(cache_ttl_seconds=10), http_transport=success_transport(calls))
    first = run(adapter.get_profile("XDevelopers"))
    second = run(adapter.get_profile("XDevelopers"))
    assert first.platform_id == second.platform_id and len(calls) == 1
    run(adapter.search_creators(DiscoveryCriteria(platforms=["x"], keywords=["@XDevelopers"])))
    assert len(calls) == 2  # search/profile namespaces do not collide
    now[0] = 111.0
    run(adapter.get_profile("XDevelopers"))
    assert len(calls) == 3
    assert all("test-bearer-token" not in repr(key) for key in adapter._cache)


def test_capability_reporting_is_conservative():
    capabilities = XApiAdapter(settings()).capabilities
    assert capabilities.keyword_search and capabilities.username_lookup
    assert capabilities.follower_metrics and capabilities.content_metrics
    assert not capabilities.category_search and not capabilities.location_filtering
    assert not capabilities.brand_discovery and not capabilities.audience_demographics


def test_research_dispatcher_uses_x_provider_without_architecture_changes():
    calls = []
    adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
    dispatcher = ResearchDispatcher([MockPlatformExecutionProvider(adapter)])
    task = ResearchTask(
        id="x-profile", type=TaskType.PROFILE_LOOKUP, platform="x",
        entity_type="creator", query="@XDevelopers", created_at=datetime.now(timezone.utc),
    )
    result = run(dispatcher.dispatch(task, DiscoveryCriteria(platforms=["x"])))
    assert result.entities and result.entities[0].source == "x_api_v2"


def test_research_dispatcher_supported_search_and_access_restriction():
    calls = []
    adapter = XApiAdapter(settings(), http_transport=success_transport(calls))
    dispatcher = ResearchDispatcher([MockPlatformExecutionProvider(adapter)])
    task = ResearchTask(
        id="x-search", type=TaskType.CREATOR_SEARCH, platform="x",
        entity_type="creator", query="software", created_at=datetime.now(timezone.utc),
    )
    criteria = DiscoveryCriteria(platforms=["x"], niche="software")
    assert run(dispatcher.dispatch(task, criteria)).entities

    restricted = XApiAdapter(
        settings(), http_transport=httpx.MockTransport(lambda request: httpx.Response(403, json={})),
    )
    dispatcher = ResearchDispatcher([MockPlatformExecutionProvider(restricted)])
    task.status = "pending"
    restricted_result = run(dispatcher.dispatch(task, criteria))
    assert restricted_result.status == "failed"
    assert restricted_result.entities == []
    assert any("failed safely" in warning for warning in restricted_result.warnings)
