import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.source_adapters import TwitchMockAdapter, build_source_adapters
from brand_discovery_ai.twitch_adapter import TwitchHelixAdapter
from brand_discovery_ai.twitch_config import TwitchConfigurationError, TwitchSettings
from brand_discovery_ai.twitch_errors import (
    TwitchDisabledError, TwitchInvalidCredentialsError, TwitchRateLimitError,
    TwitchTimeoutError, TwitchUnavailableError,
)
from brand_discovery_ai.youtube_config import YouTubeSettings
from research_agent.dispatcher import MockPlatformExecutionProvider, ResearchDispatcher
from research_agent.models import ResearchTask, TaskType


def run(coro):
    return asyncio.run(coro)


def settings(**updates):
    values = {
        "client_id": "test-client-id", "client_secret": "test-client-secret",
        "enabled": True, "timeout_seconds": 2, "max_results": 20,
    }
    values.update(updates)
    return TwitchSettings(**values)


def search_item(user_id="141981764"):
    return {
        "broadcaster_language": "en", "broadcaster_login": "twitchdev",
        "display_name": "TwitchDev", "game_id": "509658",
        "game_name": "Just Chatting", "id": user_id, "is_live": False,
        "tags": ["Software Development", "English"],
        "thumbnail_url": "https://raw.example/thumbnail.jpg", "title": "Building APIs",
    }


def user(user_id="141981764", broadcaster_type="partner"):
    return {
        "id": user_id, "login": "twitchdev", "display_name": "TwitchDev",
        "type": "", "broadcaster_type": broadcaster_type,
        "description": "Supporting third-party developers building Twitch integrations.",
        "profile_image_url": "https://raw.example/profile.png",
        "offline_image_url": "https://raw.example/offline.png",
        "view_count": 999999999,
        "created_at": "2016-12-14T20:32:28Z",
    }


def success_transport(calls, *, search_data=None, user_data=None):
    search_data = [search_item()] if search_data is None else search_data
    user_data = [user()] if user_data is None else user_data
    async def handler(request):
        calls.append(request)
        if request.url.host == "id.twitch.tv":
            return httpx.Response(200, json={"access_token": "app-token", "expires_in": 3600, "token_type": "bearer"})
        if request.url.path.endswith("/search/channels"):
            return httpx.Response(200, json={"data": search_data, "pagination": {}})
        if request.url.path.endswith("/users"):
            return httpx.Response(200, json={"data": user_data})
        return httpx.Response(404, json={"message": "not found"})
    return httpx.MockTransport(handler)


def test_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("TWITCH_CLIENT_ID", "client")
    monkeypatch.setenv("TWITCH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TWITCH_ENABLED", "true")
    monkeypatch.setenv("TWITCH_TIMEOUT_SECONDS", "7.5")
    monkeypatch.setenv("TWITCH_MAX_RESULTS", "50")
    configured = TwitchSettings.from_env()
    assert configured.client_id == "client" and configured.client_secret == "secret"
    assert configured.enabled is True and configured.timeout_seconds == 7.5
    assert configured.max_results == 50


@pytest.mark.parametrize("updates", [
    {"client_id": ""}, {"client_secret": ""}, {"timeout_seconds": 0.5},
    {"max_results": 0}, {"max_results": 101},
])
def test_invalid_configuration_is_rejected(updates):
    with pytest.raises(TwitchConfigurationError):
        settings(**updates).validate()


def test_production_factory_replaces_only_enabled_real_providers():
    adapters = build_source_adapters(
        youtube_settings=YouTubeSettings(enabled=False), twitch_settings=settings(),
    )
    assert isinstance(adapters[Platform.TWITCH], TwitchHelixAdapter)
    assert not isinstance(adapters[Platform.TWITCH], TwitchMockAdapter)
    assert adapters[Platform.INSTAGRAM].source == "mock:instagram"


def test_successful_creator_search_and_normalization():
    calls = []
    adapter = TwitchHelixAdapter(settings(max_results=10), http_transport=success_transport(calls))
    profiles = run(adapter.search_creators(DiscoveryCriteria(
        entity_type="creator", platforms=["twitch"], niche="software",
        keywords=["development"], result_limit=3,
    )))
    assert len(profiles) == 1 and len(calls) == 3
    profile = profiles[0]
    assert profile.platform_id == "141981764"
    assert profile.username == "twitchdev" and profile.display_name == "TwitchDev"
    assert profile.profile_url == "https://www.twitch.tv/twitchdev"
    assert profile.biography.startswith("Supporting third-party")
    assert profile.language == "en" and profile.categories == ["Just Chatting"]
    assert profile.keywords == ["Software Development", "English"]
    assert profile.verified is True
    assert profile.follower_count is None and profile.total_view_count is None
    assert profile.published_at.isoformat() == "2016-12-14T20:32:28+00:00"
    assert profile.source == "twitch_helix_api"
    serialized = profile.model_dump_json()
    assert "profile_image_url" not in serialized and "999999999" not in serialized
    assert any("broadcaster type: partner" in warning.casefold() for warning in profile.warnings)
    assert calls[1].url.params["first"] == "3"


def test_empty_search_does_not_fetch_users():
    calls = []
    adapter = TwitchHelixAdapter(settings(), http_transport=success_transport(calls, search_data=[]))
    result = run(adapter.search_creators(DiscoveryCriteria(platforms=["twitch"], niche="missing")))
    assert result == []
    assert [request.url.path for request in calls] == ["/oauth2/token", "/helix/search/channels"]


def test_profile_and_broadcaster_lookup_by_login_and_url():
    for lookup in ("twitchdev", "@twitchdev", "https://www.twitch.tv/twitchdev", "141981764"):
        calls = []
        adapter = TwitchHelixAdapter(settings(), http_transport=success_transport(calls))
        profile = run(adapter.get_broadcaster(lookup))
        assert profile and profile.username == "twitchdev"
        assert calls[-1].url.path.endswith("/users")


def test_invalid_credentials_are_safe_and_not_cached():
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"message": "client secret leaked detail"})
    adapter = TwitchHelixAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(TwitchInvalidCredentialsError) as caught:
        run(adapter.get_profile("twitchdev"))
    assert "test-client-secret" not in str(caught.value)
    assert "leaked detail" not in str(caught.value)
    with pytest.raises(TwitchInvalidCredentialsError):
        run(adapter.get_profile("twitchdev"))
    assert len(calls) == 2


def test_expired_token_401_triggers_one_automatic_refresh():
    token_calls, user_calls, auth_headers = 0, 0, []
    async def handler(request):
        nonlocal token_calls, user_calls
        if request.url.host == "id.twitch.tv":
            token_calls += 1
            return httpx.Response(200, json={"access_token": f"token-{token_calls}", "expires_in": 3600})
        user_calls += 1
        auth_headers.append(request.headers["Authorization"])
        if user_calls == 1:
            return httpx.Response(401, json={"message": "invalid OAuth token"})
        return httpx.Response(200, json={"data": [user()]})
    adapter = TwitchHelixAdapter(settings(), http_transport=httpx.MockTransport(handler))
    profile = run(adapter.get_profile("twitchdev"))
    assert profile and token_calls == 2 and user_calls == 2
    assert auth_headers == ["Bearer token-1", "Bearer token-2"]


def test_timeout_is_mapped_without_leaking_transport_detail():
    async def handler(request):
        if request.url.host == "id.twitch.tv":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        raise httpx.ReadTimeout("private transport detail", request=request)
    adapter = TwitchHelixAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(TwitchTimeoutError) as caught:
        run(adapter.get_profile("twitchdev"))
    assert "private transport detail" not in str(caught.value)
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("status,error_type", [(429, TwitchRateLimitError), (503, TwitchUnavailableError)])
def test_rate_limit_and_service_unavailable_are_mapped(status, error_type):
    async def handler(request):
        if request.url.host == "id.twitch.tv":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        return httpx.Response(status, json={"message": "private upstream detail"})
    adapter = TwitchHelixAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(error_type) as caught:
        run(adapter.get_profile("twitchdev"))
    assert "private upstream detail" not in str(caught.value)


def test_successful_responses_are_cached_but_tokens_are_reused():
    calls = []
    adapter = TwitchHelixAdapter(settings(), http_transport=success_transport(calls))
    criteria = DiscoveryCriteria(platforms=["twitch"], niche="software")
    first = run(adapter.search_creators(criteria))
    second = run(adapter.search_creators(criteria))
    assert first[0].platform_id == second[0].platform_id
    assert len(calls) == 3  # token, search, batched users


def test_affiliate_status_does_not_fabricate_verification():
    calls = []
    adapter = TwitchHelixAdapter(
        settings(), http_transport=success_transport(calls, user_data=[user(broadcaster_type="affiliate")]),
    )
    profile = run(adapter.get_profile("twitchdev"))
    assert profile.verified is None
    assert any("affiliate status does not establish" in warning.casefold() for warning in profile.warnings)


def test_disabled_adapter_never_requests_token_or_helix():
    calls = []
    adapter = TwitchHelixAdapter(
        settings(enabled=False, client_id="", client_secret=""),
        http_transport=success_transport(calls),
    )
    assert run(adapter.health_check())["status"] == "disabled"
    with pytest.raises(TwitchDisabledError):
        run(adapter.get_profile("twitchdev"))
    assert calls == []


def test_existing_research_dispatcher_accepts_twitch_source_provider_unchanged():
    calls = []
    adapter = TwitchHelixAdapter(settings(), http_transport=success_transport(calls))
    dispatcher = ResearchDispatcher([MockPlatformExecutionProvider(adapter)])
    task = ResearchTask(
        id="twitch-creator-search", type=TaskType.CREATOR_SEARCH,
        platform="twitch", entity_type="creator", query="software",
        created_at=datetime.now(timezone.utc),
    )
    result = run(dispatcher.dispatch(task, DiscoveryCriteria(platforms=["twitch"], niche="software")))
    assert result.entities and result.entities[0].source == "twitch_helix_api"
