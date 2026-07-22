"""Vendor-neutral source interface and deterministic, network-free platform mocks."""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .discovery_schemas import AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform
from .normalization import normalize_payload


MOCK_COLLECTED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


CAPABILITY_REGISTRY: dict[Platform, AdapterCapabilities] = {
    Platform.INSTAGRAM: AdapterCapabilities(keyword_search=True, category_search=True, username_lookup=True, location_filtering=False, follower_metrics=True, content_metrics=True, audience_demographics=False, brand_discovery=True, creator_discovery=True),
    Platform.YOUTUBE: AdapterCapabilities(keyword_search=True, category_search=True, username_lookup=True, location_filtering=False, follower_metrics=True, content_metrics=True, audience_demographics=False, brand_discovery=True, creator_discovery=True),
    Platform.SNAPCHAT: AdapterCapabilities(keyword_search=False, category_search=False, username_lookup=True, location_filtering=False, follower_metrics=False, content_metrics=False, audience_demographics=False, brand_discovery=False, creator_discovery=True),
    Platform.TWITCH: AdapterCapabilities(keyword_search=True, category_search=True, username_lookup=True, location_filtering=False, follower_metrics=True, content_metrics=True, audience_demographics=False, brand_discovery=False, creator_discovery=True),
    Platform.X: AdapterCapabilities(keyword_search=True, category_search=False, username_lookup=True, location_filtering=False, follower_metrics=True, content_metrics=True, audience_demographics=False, brand_discovery=True, creator_discovery=True),
}


class SourceProvider(ABC):
    platform: Platform

    @abstractmethod
    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]: ...

    @abstractmethod
    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]: ...

    @abstractmethod
    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None: ...

    @abstractmethod
    async def health_check(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities: ...


class DeterministicMockAdapter(SourceProvider):
    platform: Platform

    @property
    def capabilities(self) -> AdapterCapabilities:
        return CAPABILITY_REGISTRY[self.platform]

    @property
    def source(self) -> str:
        return f"mock:{self.platform.value}"

    async def health_check(self) -> dict[str, Any]:
        return {"status": "ok", "platform": self.platform.value, "mock": True, "network": False}

    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        if not self.capabilities.creator_discovery:
            return []
        return self._search("creator", criteria)

    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        if not self.capabilities.brand_discovery:
            return []
        return self._search("brand", criteria)

    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None:
        needle = platform_id_or_username.lstrip("@").casefold()
        for payload in self._payloads():
            if str(payload["id"]).casefold() == needle or str(payload.get("username", "")).casefold() == needle:
                return normalize_payload(self.platform, deepcopy(payload), self.source)
        return None

    def _search(self, entity_type: str, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        terms = {v.casefold() for v in [criteria.niche, *criteria.categories, *criteria.keywords] if v}
        excluded = {v.casefold() for v in criteria.exclusions}
        results = []
        for raw in self._payloads():
            if raw["entity_type"] != entity_type:
                continue
            haystack = " ".join(str(v) for v in [raw.get("username"), raw.get("display_name"), raw.get("biography"), *(raw.get("categories") or []), *(raw.get("keywords") or [])]).casefold()
            if excluded and any(term in haystack for term in excluded):
                continue
            if terms and self.capabilities.keyword_search and not any(term in haystack for term in terms):
                continue
            results.append(normalize_payload(self.platform, deepcopy(raw), self.source))
        return results

    def _payloads(self) -> list[dict[str, Any]]:
        spec = _PLATFORM_DATA[self.platform]
        return [dict(item, collected_at=MOCK_COLLECTED_AT, source_confidence=0.82) for item in spec]


class InstagramMockAdapter(DeterministicMockAdapter): platform = Platform.INSTAGRAM
class YouTubeMockAdapter(DeterministicMockAdapter): platform = Platform.YOUTUBE
class SnapchatMockAdapter(DeterministicMockAdapter): platform = Platform.SNAPCHAT
class TwitchMockAdapter(DeterministicMockAdapter): platform = Platform.TWITCH
class XMockAdapter(DeterministicMockAdapter): platform = Platform.X


def build_mock_adapters() -> dict[Platform, SourceProvider]:
    adapters = [InstagramMockAdapter(), YouTubeMockAdapter(), SnapchatMockAdapter(), TwitchMockAdapter(), XMockAdapter()]
    return {adapter.platform: adapter for adapter in adapters}


def build_source_adapters(*, youtube_settings=None, youtube_http_transport=None) -> dict[Platform, SourceProvider]:
    """Production factory: YouTube is real; other platforms remain explicit mocks."""
    from .youtube_adapter import YouTubeDataAPIAdapter
    from .youtube_config import YouTubeSettings

    adapters = build_mock_adapters()
    settings = youtube_settings or YouTubeSettings.from_env()
    adapters[Platform.YOUTUBE] = YouTubeDataAPIAdapter(
        settings, http_transport=youtube_http_transport,
    )
    return adapters


def _profile(platform: Platform, entity: str, index: int, **overrides: Any) -> dict[str, Any]:
    handle = overrides.pop("username", f"{entity}_{platform.value}_{index}")
    hosts = {Platform.INSTAGRAM: "instagram.com", Platform.YOUTUBE: "youtube.com", Platform.SNAPCHAT: "snapchat.com", Platform.TWITCH: "twitch.tv", Platform.X: "x.com"}
    base = {
        "id": f"{platform.value}-{entity}-{index}", "entity_type": entity, "username": handle,
        "display_name": f"{entity.title()} {platform.value.title()} {index}",
        "profile_url": f"https://{hosts[platform]}/{handle}",
        "biography": "Sustainable fashion, fitness and technology campaign content.",
        "categories": ["sustainable fashion", "lifestyle"], "keywords": ["ethical", "fitness", "technology"],
        "location": "Mumbai, India", "language": "en", "follower_count": 25000 + index * 5000,
        "following_count": 420, "content_count": 180, "average_views": 9000,
        "average_likes": 1200, "average_comments": 85, "engagement_rate": 5.14,
        "verified": index == 1, "website": f"https://{handle}.example.com",
        "business_email_available": entity == "brand", "warnings": ["Synthetic mock profile; verify against the platform before use."],
    }
    base.update(overrides)
    return base


_PLATFORM_DATA: dict[Platform, list[dict[str, Any]]] = {
    platform: [_profile(platform, "creator", 1), _profile(platform, "creator", 2), _profile(platform, "brand", 1), _profile(platform, "brand", 2)]
    for platform in Platform
}
# Model legitimate platform gaps explicitly; never fill them with synthetic zeros.
for item in _PLATFORM_DATA[Platform.SNAPCHAT]:
    for key in ("follower_count", "following_count", "content_count", "average_views", "average_likes", "average_comments", "engagement_rate"):
        item[key] = None
for platform in (Platform.INSTAGRAM, Platform.YOUTUBE, Platform.SNAPCHAT, Platform.TWITCH, Platform.X):
    for item in _PLATFORM_DATA[platform]:
        item["audience_demographics"] = None
