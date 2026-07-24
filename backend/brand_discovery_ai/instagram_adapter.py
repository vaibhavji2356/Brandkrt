"""Official Instagram Graph API provider using hashtag and business discovery."""

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from .discovery_schemas import AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform
from .instagram_config import InstagramSettings
from .instagram_errors import (
    InstagramAdapterError, InstagramAuthenticationError, InstagramDisabledError,
    InstagramRateLimitError, InstagramResponseError, InstagramTimeoutError,
)
from .normalization import normalize_payload
from .source_adapters import SourceProvider


GRAPH_BASE_URL = "https://graph.facebook.com"
PROFILE_FIELDS = (
    "id,username,name,biography,website,followers_count,follows_count,media_count"
)


class InstagramGraphAPIAdapter(SourceProvider):
    platform = Platform.INSTAGRAM

    def __init__(self, settings: InstagramSettings, *, http_transport=None, base_url=GRAPH_BASE_URL):
        self.settings = settings.validate()
        self._transport = http_transport
        self._base_url = f"{base_url.rstrip('/')}/{settings.api_version}"

    @property
    def capabilities(self) -> AdapterCapabilities:
        enabled = self.settings.enabled
        return AdapterCapabilities(
            keyword_search=enabled, category_search=enabled, username_lookup=enabled,
            location_filtering=False, follower_metrics=enabled, content_metrics=enabled,
            audience_demographics=False, brand_discovery=enabled, creator_discovery=enabled,
        )

    async def health_check(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "platform": "instagram", "network": False}
        return {"status": "configured", "platform": "instagram", "network": True}

    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        return await self._search(criteria, "creator")

    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        return await self._search(criteria, "brand")

    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None:
        username = _username(platform_id_or_username)
        if not username:
            return None
        profile = await self._business_discovery(username)
        return self._normalize(profile, "brand", []) if profile else None

    async def _search(self, criteria: DiscoveryCriteria, entity_type: str) -> list[NormalizedProfile]:
        terms = _terms(criteria)
        if not terms:
            return []
        usernames: list[str] = []
        media_by_username: dict[str, list[dict[str, Any]]] = {}
        for term in terms[:3]:
            hashtag = await self._request("ig_hashtag_search", {
                "user_id": self.settings.user_id, "q": term,
            })
            data = hashtag.get("data", [])
            if not data:
                continue
            recent = await self._request(f"{data[0]['id']}/recent_media", {
                "user_id": self.settings.user_id,
                "fields": "id,caption,comments_count,like_count,permalink,timestamp,username",
                "limit": str(min(criteria.result_limit, self.settings.max_results)),
            })
            for media in recent.get("data", []):
                username = media.get("username")
                if isinstance(username, str) and username and username not in usernames:
                    usernames.append(username)
                if isinstance(username, str):
                    media_by_username.setdefault(username, []).append(media)
        profiles = []
        exclusions = {item.casefold() for item in criteria.exclusions}
        for username in usernames:
            if len(profiles) >= min(criteria.result_limit, self.settings.max_results):
                break
            profile = await self._business_discovery(username)
            if not profile:
                continue
            text = " ".join(str(profile.get(key, "")) for key in ("username", "name", "biography")).casefold()
            if exclusions and any(item in text for item in exclusions):
                continue
            profiles.append(self._normalize(profile, entity_type, media_by_username.get(username, [])))
        return profiles

    async def _business_discovery(self, username: str) -> dict[str, Any] | None:
        payload = await self._request(self.settings.user_id, {
            "fields": f"business_discovery.username({username}){{{PROFILE_FIELDS}}}",
        }, allow_not_found=True)
        value = payload.get("business_discovery")
        return value if isinstance(value, dict) else None

    async def _request(self, resource: str, params: dict[str, str], *, allow_not_found=False) -> dict[str, Any]:
        if not self.settings.enabled:
            raise InstagramDisabledError("Instagram integration is disabled.")
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=httpx.Timeout(self.settings.timeout_seconds),
            ) as client:
                response = await client.get(
                    f"{self._base_url}/{resource}",
                    params={**params, "access_token": self.settings.access_token},
                )
        except httpx.TimeoutException:
            raise InstagramTimeoutError("Instagram request timed out.") from None
        except httpx.RequestError:
            raise InstagramAdapterError("Instagram request failed.") from None
        if response.status_code >= 400:
            if allow_not_found and response.status_code in {400, 404}:
                return {}
            _raise_api_error(response)
        try:
            payload = response.json()
        except ValueError:
            raise InstagramResponseError("Instagram returned an invalid response.") from None
        if not isinstance(payload, dict):
            raise InstagramResponseError("Instagram returned an invalid response.")
        return payload

    def _normalize(self, profile: dict[str, Any], entity_type: str, media: list[dict[str, Any]]) -> NormalizedProfile:
        likes = [item.get("like_count") for item in media if isinstance(item.get("like_count"), int)]
        comments = [item.get("comments_count") for item in media if isinstance(item.get("comments_count"), int)]
        username = str(profile.get("username", "")).strip()
        return normalize_payload(Platform.INSTAGRAM, {
            "id": profile["id"], "entity_type": entity_type, "username": username,
            "display_name": profile.get("name"), "profile_url": f"https://www.instagram.com/{username}/",
            "biography": profile.get("biography"), "website": profile.get("website"),
            "categories": [], "keywords": [], "location": None, "language": None,
            "follower_count": profile.get("followers_count"),
            "following_count": profile.get("follows_count"),
            "content_count": profile.get("media_count"),
            "average_likes": round(sum(likes) / len(likes)) if likes else None,
            "average_comments": round(sum(comments) / len(comments)) if comments else None,
            "verified": None, "audience_demographics": None,
            "collected_at": datetime.now(timezone.utc), "source_confidence": 0.96,
            "warnings": [
                "Instagram business discovery covers professional accounts accessible to the authenticated account.",
                "Entity type reflects the requested discovery context; Instagram does not return a brand/creator classification.",
            ],
        }, "instagram_graph_api")


def _terms(criteria: DiscoveryCriteria) -> list[str]:
    values = [criteria.niche, *criteria.categories, *criteria.keywords]
    result = []
    for value in values:
        cleaned = re.sub(r"[^a-zA-Z0-9_]", "", value or "").lstrip("#")[:100]
        if cleaned and cleaned.casefold() not in {item.casefold() for item in result}:
            result.append(cleaned)
    return result


def _username(value: str) -> str | None:
    candidate = value.strip()
    if candidate.startswith(("http://", "https://")):
        parts = urlsplit(candidate)
        if (parts.hostname or "").casefold() not in {"instagram.com", "www.instagram.com"}:
            return None
        segments = [item for item in parts.path.split("/") if item]
        candidate = segments[0] if len(segments) == 1 else ""
    candidate = candidate.lstrip("@")
    return candidate if re.fullmatch(r"[A-Za-z0-9._]{1,30}", candidate) else None


def _raise_api_error(response: httpx.Response) -> None:
    try:
        error = response.json().get("error", {})
    except ValueError:
        error = {}
    code = error.get("code")
    if response.status_code in {401, 403} or code in {190, 200}:
        raise InstagramAuthenticationError("Instagram credentials or permissions are invalid.")
    if response.status_code == 429 or code in {4, 17, 32, 613}:
        raise InstagramRateLimitError("Instagram API rate limit reached.")
    raise InstagramAdapterError("Instagram API request was rejected.")
