"""Real YouTube Data API v3 SourceProvider with bounded caching and safe errors."""

from copy import deepcopy
from datetime import datetime, timezone
import re
import shlex
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .discovery_schemas import AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform
from .normalization import normalize_payload
from .source_adapters import SourceProvider
from .youtube_config import YouTubeSettings
from .youtube_errors import (
    YouTubeAdapterError, YouTubeDisabledError, YouTubeInvalidKeyError,
    YouTubeQuotaError, YouTubeResponseError, YouTubeTimeoutError,
)


YOUTUBE_API_BASE_URL = "https://www.googleapis.com/youtube/v3"
CHANNEL_PARTS = "snippet,statistics,brandingSettings,topicDetails"
QUOTA_REASONS = {
    "quotaExceeded", "dailyLimitExceeded", "dailyLimitExceededUnreg",
    "rateLimitExceeded", "userRateLimitExceeded", "limitExceeded",
}
INVALID_KEY_REASONS = {"keyInvalid", "apiKeyInvalid", "badRequest"}
DISABLED_REASONS = {"accessNotConfigured", "apiNotActivated", "serviceDisabled"}


class YouTubeDataAPIAdapter(SourceProvider):
    platform = Platform.YOUTUBE

    def __init__(
        self,
        settings: YouTubeSettings,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = YOUTUBE_API_BASE_URL,
    ):
        self.settings = settings.validate()
        self._transport = http_transport
        self._base_url = base_url.rstrip("/")
        self._cache: dict[tuple, tuple[float, dict[str, Any]]] = {}

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            keyword_search=True, category_search=False, username_lookup=True,
            location_filtering=False, follower_metrics=True, content_metrics=True,
            audience_demographics=False, brand_discovery=False, creator_discovery=True,
        )

    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        query = " ".join(filter(None, [criteria.niche, *criteria.categories, *criteria.keywords])).strip()
        if not query:
            return []
        maximum = min(self.settings.max_results, criteria.result_limit, 50)
        search = await self._request("search", {
            "part": "snippet", "type": "channel", "q": query,
            "maxResults": str(maximum),
        })
        channel_ids = []
        for item in _items(search):
            channel_id = (item.get("id") or {}).get("channelId")
            if isinstance(channel_id, str) and channel_id and channel_id not in channel_ids:
                channel_ids.append(channel_id)
        if not channel_ids:
            return []
        details = await self._channels({"id": ",".join(channel_ids)})
        by_id = {item.get("id"): item for item in details if isinstance(item.get("id"), str)}
        profiles = [self._normalize(by_id[channel_id], "creator") for channel_id in channel_ids if channel_id in by_id]
        exclusions = {value.casefold() for value in criteria.exclusions}
        if exclusions:
            profiles = [profile for profile in profiles if not any(value in _profile_text(profile) for value in exclusions)]
        return profiles

    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        del criteria
        # The public API does not provide a reliable creator-vs-brand classification.
        return []

    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None:
        lookup = _parse_lookup(platform_id_or_username)
        if lookup is None:
            return None
        filter_name, value = lookup
        details = await self._channels({filter_name: value})
        return self._normalize(details[0], "creator") if details else None

    async def health_check(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "platform": "youtube", "network": False}
        if not self.settings.api_key:
            return {"status": "misconfigured", "platform": "youtube", "network": False}
        return {"status": "configured", "platform": "youtube", "network": True}

    async def _channels(self, channel_filter: dict[str, str]) -> list[dict[str, Any]]:
        response = await self._request("channels", {"part": CHANNEL_PARTS, **channel_filter})
        return _items(response)

    async def _request(self, resource: str, params: dict[str, str]) -> dict[str, Any]:
        if not self.settings.enabled:
            raise YouTubeDisabledError("YouTube integration is disabled.")
        cache_key = (resource, tuple(sorted(params.items())))
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return deepcopy(cached[1])
        request_params = {**params, "key": self.settings.api_key}
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=httpx.Timeout(self.settings.timeout_seconds),
            ) as client:
                response = await client.get(f"{self._base_url}/{resource}", params=request_params)
        except httpx.TimeoutException as exc:
            del exc
            raise YouTubeTimeoutError("YouTube request timed out.") from None
        except httpx.RequestError as exc:
            del exc
            raise YouTubeAdapterError("YouTube request failed.") from None
        if response.status_code >= 400:
            _raise_api_error(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise YouTubeResponseError("YouTube returned an invalid response.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items", []), list):
            raise YouTubeResponseError("YouTube returned an invalid response.")
        self._cache[cache_key] = (now + self.settings.cache_ttl_seconds, deepcopy(payload))
        return payload

    def _normalize(self, channel: dict[str, Any], entity_type: str) -> NormalizedProfile:
        channel_id = channel.get("id")
        if not isinstance(channel_id, str) or not channel_id:
            raise YouTubeResponseError("YouTube channel response omitted its identifier.")
        snippet = channel.get("snippet") if isinstance(channel.get("snippet"), dict) else {}
        statistics = channel.get("statistics") if isinstance(channel.get("statistics"), dict) else {}
        branding = channel.get("brandingSettings") if isinstance(channel.get("brandingSettings"), dict) else {}
        branding_channel = branding.get("channel") if isinstance(branding.get("channel"), dict) else {}
        custom_url = snippet.get("customUrl") if isinstance(snippet.get("customUrl"), str) else None
        hidden = statistics.get("hiddenSubscriberCount") is True
        warnings = [
            "YouTube Data API does not expose public channel verification status; verified is unavailable.",
            "YouTube subscriber counts may be rounded according to YouTube policy.",
        ]
        if hidden:
            warnings.append("The channel hides its subscriber count.")
        topics = channel.get("topicDetails") if isinstance(channel.get("topicDetails"), dict) else {}
        categories = [_topic_name(value) for value in topics.get("topicCategories", []) if isinstance(value, str)]
        keywords = _keywords(branding_channel.get("keywords"))
        payload = {
            "id": channel_id, "entity_type": entity_type,
            "username": custom_url.lstrip("@") if custom_url else None,
            "display_name": snippet.get("title"),
            "profile_url": f"https://www.youtube.com/channel/{channel_id}",
            "biography": snippet.get("description"), "categories": categories,
            "keywords": keywords, "location": snippet.get("country"),
            "language": branding_channel.get("defaultLanguage"),
            "follower_count": None if hidden else _nonnegative_int(statistics.get("subscriberCount")),
            "following_count": None, "content_count": _nonnegative_int(statistics.get("videoCount")),
            "total_view_count": _nonnegative_int(statistics.get("viewCount")),
            "average_views": None, "average_likes": None, "average_comments": None,
            "engagement_rate": None, "verified": None, "website": None,
            "business_email_available": None, "audience_demographics": None,
            "published_at": snippet.get("publishedAt"),
            "source_confidence": 0.98, "collected_at": datetime.now(timezone.utc),
            "warnings": warnings,
        }
        return normalize_payload(Platform.YOUTUBE, payload, "youtube_data_api_v3")


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items", [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise YouTubeResponseError("YouTube returned invalid resource items.")
    return items


def _parse_lookup(value: str) -> tuple[str, str] | None:
    candidate = value.strip()
    if not candidate or len(candidate) > 200 or re.search(r"[\x00-\x1f]", candidate):
        return None
    if candidate.startswith(("http://", "https://")):
        parts = urlsplit(candidate)
        if (parts.hostname or "").casefold() not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
            return None
        segments = [segment for segment in parts.path.split("/") if segment]
        if len(segments) >= 2 and segments[0] == "channel":
            candidate = segments[1]
        elif segments and segments[0].startswith("@"):
            return "forHandle", segments[0]
        elif len(segments) >= 2 and segments[0] == "user":
            return "forUsername", segments[1]
        else:
            return None
    if re.fullmatch(r"UC[A-Za-z0-9_-]{20,}", candidate):
        return "id", candidate
    handle = candidate if candidate.startswith("@") else f"@{candidate}"
    return ("forHandle", handle) if re.fullmatch(r"@[A-Za-z0-9._-]{3,100}", handle) else None


def _raise_api_error(response: httpx.Response) -> None:
    reasons = set()
    try:
        payload = response.json()
        errors = ((payload.get("error") or {}).get("errors") or []) if isinstance(payload, dict) else []
        reasons = {item.get("reason") for item in errors if isinstance(item, dict) and isinstance(item.get("reason"), str)}
        status = (payload.get("error") or {}).get("status") if isinstance(payload, dict) else None
        if isinstance(status, str):
            reasons.add(status)
    except ValueError:
        pass
    if reasons & QUOTA_REASONS or response.status_code == 429:
        raise YouTubeQuotaError("YouTube quota is unavailable.")
    if reasons & DISABLED_REASONS:
        raise YouTubeDisabledError("YouTube Data API is disabled for this project.")
    if reasons & INVALID_KEY_REASONS or response.status_code in {401}:
        raise YouTubeInvalidKeyError("YouTube API key is invalid.")
    raise YouTubeAdapterError("YouTube API request was rejected.")


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _keywords(value: Any) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        values = shlex.split(value)
    except ValueError:
        values = value.split()
    return list(dict.fromkeys(item.strip()[:80] for item in values if item.strip()))[:50]


def _topic_name(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].replace("_", " ")[:120]


def _profile_text(profile: NormalizedProfile) -> str:
    return " ".join(filter(None, [profile.username, profile.display_name, profile.biography, *profile.categories, *profile.keywords])).casefold()
