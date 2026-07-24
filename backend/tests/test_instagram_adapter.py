import asyncio
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.instagram_adapter import InstagramGraphAPIAdapter
from brand_discovery_ai.instagram_config import InstagramConfigurationError, InstagramSettings
from brand_discovery_ai.instagram_errors import (
    InstagramAuthenticationError, InstagramDisabledError, InstagramRateLimitError,
)
from brand_discovery_ai.source_adapters import InstagramMockAdapter, build_source_adapters


def run(coro):
    return asyncio.run(coro)


def settings(**updates):
    values = {
        "enabled": True, "access_token": "test-token", "user_id": "17841400000000000",
        "api_version": "v25.0", "timeout_seconds": 2, "max_results": 10,
    }
    values.update(updates)
    return InstagramSettings(**values)


def transport(calls):
    async def handler(request):
        calls.append(request)
        if request.url.path.endswith("/ig_hashtag_search"):
            return httpx.Response(200, json={"data": [{"id": "17843800000000001"}]})
        if request.url.path.endswith("/recent_media"):
            return httpx.Response(200, json={"data": [{
                "id": "media-1", "username": "ethicalbrand", "caption": "Sustainable launch",
                "like_count": 120, "comments_count": 8, "timestamp": "2026-07-20T10:00:00Z",
            }]})
        if request.url.path.endswith("/17841400000000000"):
            return httpx.Response(200, json={"business_discovery": {
                "id": "17841411111111111", "username": "ethicalbrand",
                "name": "Ethical Brand", "biography": "Sustainable fashion from Mumbai",
                "website": "https://ethical.example", "followers_count": 25000,
                "follows_count": 300, "media_count": 180,
            }})
        return httpx.Response(404, json={"error": {"code": 100}})
    return httpx.MockTransport(handler)


def test_environment_configuration(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123")
    configured = InstagramSettings.from_env()
    assert configured.enabled and configured.access_token == "token"
    assert configured.user_id == "123" and configured.api_version == "v25.0"


def test_enabled_configuration_requires_credentials():
    with pytest.raises(InstagramConfigurationError):
        settings(access_token="").validate()


def test_factory_replaces_instagram_mock():
    adapters = build_source_adapters(instagram_settings=settings())
    assert isinstance(adapters[Platform.INSTAGRAM], InstagramGraphAPIAdapter)
    assert not isinstance(adapters[Platform.INSTAGRAM], InstagramMockAdapter)


def test_hashtag_brand_search_returns_normalized_factual_profile():
    calls = []
    adapter = InstagramGraphAPIAdapter(settings(), http_transport=transport(calls))
    profiles = run(adapter.search_brands(DiscoveryCriteria(
        entity_type="brand", platforms=["instagram"], niche="sustainable fashion",
        result_limit=5,
    )))
    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.platform == Platform.INSTAGRAM
    assert profile.entity_type == "brand" and profile.username == "ethicalbrand"
    assert profile.follower_count == 25000 and profile.content_count == 180
    assert profile.average_likes == 120 and profile.average_comments == 8
    assert profile.source == "instagram_graph_api"
    assert len(calls) == 3
    assert calls[0].url.params["q"] == "sustainablefashion"
    assert calls[0].url.params["access_token"] == "test-token"


@pytest.mark.parametrize("lookup", [
    "@ethicalbrand", "ethicalbrand", "https://www.instagram.com/ethicalbrand/",
])
def test_business_profile_lookup(lookup):
    calls = []
    adapter = InstagramGraphAPIAdapter(settings(), http_transport=transport(calls))
    profile = run(adapter.get_profile(lookup))
    assert profile and profile.username == "ethicalbrand"
    assert "business_discovery.username(ethicalbrand)" in calls[0].url.params["fields"]


def test_disabled_health_and_request():
    adapter = InstagramGraphAPIAdapter(settings(enabled=False, access_token="", user_id=""))
    assert run(adapter.health_check())["status"] == "disabled"
    with pytest.raises(InstagramDisabledError):
        run(adapter.search_brands(DiscoveryCriteria(platforms=["instagram"], niche="fashion")))


@pytest.mark.parametrize(("status", "code", "error"), [
    (401, 190, InstagramAuthenticationError),
    (429, 4, InstagramRateLimitError),
])
def test_api_errors_are_safe(status, code, error):
    async def handler(_request):
        return httpx.Response(status, json={"error": {"code": code, "message": "secret-detail"}})
    adapter = InstagramGraphAPIAdapter(settings(), http_transport=httpx.MockTransport(handler))
    with pytest.raises(error) as caught:
        run(adapter.search_brands(DiscoveryCriteria(platforms=["instagram"], niche="fashion")))
    assert "secret-detail" not in str(caught.value)
    assert "test-token" not in str(caught.value)
