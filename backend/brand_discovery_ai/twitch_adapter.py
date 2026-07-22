"""Production Twitch Helix adapter using an OAuth app access token."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import re
import time
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx

from .discovery_schemas import AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform
from .normalization import normalize_payload
from .source_adapters import SourceProvider
from .twitch_config import TwitchSettings
from .twitch_errors import (
    TwitchAdapterError, TwitchDisabledError, TwitchInvalidCredentialsError,
    TwitchRateLimitError, TwitchResponseError, TwitchTimeoutError,
    TwitchUnavailableError,
)


TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_HELIX_URL = "https://api.twitch.tv/helix"


class TwitchHelixAdapter(SourceProvider):
    platform = Platform.TWITCH

    def __init__(
        self,
        settings: TwitchSettings,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        token_url: str = TWITCH_TOKEN_URL,
        helix_url: str = TWITCH_HELIX_URL,
    ):
        self.settings = settings.validate()
        self._transport = http_transport
        self._token_url = token_url
        self._helix_url = helix_url.rstrip("/")
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._cache: dict[tuple, tuple[float, dict[str, Any]]] = {}

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            keyword_search=True, category_search=True, username_lookup=True,
            location_filtering=False, follower_metrics=False, content_metrics=False,
            audience_demographics=False, brand_discovery=False, creator_discovery=True,
        )

    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        query = " ".join(filter(None, [criteria.niche, *criteria.categories, *criteria.keywords])).strip()
        if not query:
            return []
        maximum = min(self.settings.max_results, criteria.result_limit, 100)
        search_payload = await self._request("search/channels", [
            ("query", query), ("first", str(maximum)), ("live_only", "false"),
        ])
        search_items = _data(search_payload)
        channel_ids = list(dict.fromkeys(
            item.get("id") for item in search_items if isinstance(item.get("id"), str) and item.get("id")
        ))
        if not channel_ids:
            return []
        users_payload = await self._request("users", [("id", channel_id) for channel_id in channel_ids])
        users = {item.get("id"): item for item in _data(users_payload) if isinstance(item.get("id"), str)}
        search_by_id = {item.get("id"): item for item in search_items if isinstance(item.get("id"), str)}
        profiles = [
            self._normalize(users[channel_id], search_by_id.get(channel_id))
            for channel_id in channel_ids if channel_id in users
        ]
        exclusions = {value.casefold() for value in criteria.exclusions}
        if exclusions:
            profiles = [profile for profile in profiles if not any(value in _profile_text(profile) for value in exclusions)]
        return profiles

    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        del criteria
        return []

    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None:
        lookup = _parse_lookup(platform_id_or_username)
        if lookup is None:
            return None
        field, value = lookup
        payload = await self._request("users", [(field, value)])
        users = _data(payload)
        return self._normalize(users[0], None) if users else None

    async def get_broadcaster(self, platform_id_or_username: str) -> NormalizedProfile | None:
        return await self.get_profile(platform_id_or_username)

    async def health_check(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "platform": "twitch", "network": False}
        return {"status": "configured", "platform": "twitch", "network": True}

    async def _request(self, endpoint: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        if not self.settings.enabled:
            raise TwitchDisabledError("Twitch integration is disabled.")
        cache_key = (endpoint, tuple(sorted(params)))
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached[0] > now:
            return deepcopy(cached[1])

        for attempt in range(2):
            token = await self._get_token(force_refresh=attempt == 1)
            headers = {"Authorization": f"Bearer {token}", "Client-Id": self.settings.client_id}
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=httpx.Timeout(self.settings.timeout_seconds),
                ) as client:
                    response = await client.get(f"{self._helix_url}/{endpoint}", params=params, headers=headers)
            except httpx.TimeoutException:
                raise TwitchTimeoutError("Twitch request timed out.") from None
            except httpx.RequestError:
                raise TwitchUnavailableError("Twitch service is unavailable.") from None
            if response.status_code == 401 and attempt == 0:
                self._invalidate_token()
                continue
            if response.status_code >= 400:
                _raise_helix_error(response)
            payload = _json_object(response)
            if not isinstance(payload.get("data", []), list):
                raise TwitchResponseError("Twitch returned an invalid response.")
            self._cache[cache_key] = (
                time.monotonic() + self.settings.cache_ttl_seconds, deepcopy(payload),
            )
            return payload
        raise TwitchInvalidCredentialsError("Twitch credentials or token are invalid.")

    async def _get_token(self, *, force_refresh: bool = False) -> str:
        if not self.settings.enabled:
            raise TwitchDisabledError("Twitch integration is disabled.")
        now = time.monotonic()
        if not force_refresh and self._token and self._token_expires_at - now > 30:
            return self._token
        async with self._token_lock:
            now = time.monotonic()
            if not force_refresh and self._token and self._token_expires_at - now > 30:
                return self._token
            try:
                async with httpx.AsyncClient(
                    transport=self._transport, timeout=httpx.Timeout(self.settings.timeout_seconds),
                ) as client:
                    response = await client.post(self._token_url, data={
                        "client_id": self.settings.client_id,
                        "client_secret": self.settings.client_secret,
                        "grant_type": "client_credentials",
                    })
            except httpx.TimeoutException:
                raise TwitchTimeoutError("Twitch authentication timed out.") from None
            except httpx.RequestError:
                raise TwitchUnavailableError("Twitch authentication is unavailable.") from None
            if response.status_code in {400, 401, 403}:
                raise TwitchInvalidCredentialsError("Twitch client credentials are invalid.")
            if response.status_code == 429:
                raise TwitchRateLimitError("Twitch authentication is rate limited.")
            if response.status_code >= 500:
                raise TwitchUnavailableError("Twitch authentication is unavailable.")
            if response.status_code >= 400:
                raise TwitchAdapterError("Twitch authentication failed.")
            payload = _json_object(response)
            token = payload.get("access_token")
            expires_in = payload.get("expires_in")
            if not isinstance(token, str) or not token or not isinstance(expires_in, int) or expires_in <= 0:
                raise TwitchResponseError("Twitch returned an invalid token response.")
            self._token = token
            self._token_expires_at = time.monotonic() + expires_in
            return token

    def _invalidate_token(self) -> None:
        self._token = None
        self._token_expires_at = 0.0

    def _normalize(self, user: dict[str, Any], search: dict[str, Any] | None) -> NormalizedProfile:
        user_id = user.get("id")
        login = user.get("login")
        if not isinstance(user_id, str) or not user_id or not isinstance(login, str) or not login:
            raise TwitchResponseError("Twitch user response omitted required identity fields.")
        broadcaster_type = user.get("broadcaster_type") if user.get("broadcaster_type") in {"partner", "affiliate", ""} else ""
        warnings = [
            "Twitch follower count requires user-authorized broadcaster or moderator access and is unavailable with app credentials.",
            "Twitch profile image is available from Helix but is not represented by the current normalized schema.",
        ]
        if broadcaster_type:
            warnings.append(f"Twitch broadcaster type: {broadcaster_type}.")
        if broadcaster_type == "affiliate":
            warnings.append("Affiliate status does not establish verified status.")
        if search is None:
            warnings.append("Broadcaster language is unavailable from the Twitch user lookup endpoint.")
        categories = []
        keywords = []
        language = None
        if search:
            game_name = search.get("game_name")
            if isinstance(game_name, str) and game_name.strip():
                categories.append(game_name.strip()[:120])
            keywords = [tag.strip()[:80] for tag in search.get("tags", []) if isinstance(tag, str) and tag.strip()][:50]
            language = search.get("broadcaster_language") if isinstance(search.get("broadcaster_language"), str) else None
        payload = {
            "id": user_id, "entity_type": "creator", "username": login,
            "display_name": user.get("display_name"),
            "profile_url": f"https://www.twitch.tv/{login.casefold()}",
            "biography": user.get("description"), "categories": categories,
            "keywords": keywords, "location": None, "language": language,
            "follower_count": None, "following_count": None, "content_count": None,
            "total_view_count": None, "average_views": None, "average_likes": None,
            "average_comments": None, "engagement_rate": None,
            "verified": True if broadcaster_type == "partner" else None,
            "website": None, "business_email_available": None,
            "audience_demographics": None, "published_at": user.get("created_at"),
            "source_confidence": 0.98, "collected_at": datetime.now(timezone.utc),
            "warnings": warnings,
        }
        return normalize_payload(Platform.TWITCH, payload, "twitch_helix_api")


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        raise TwitchResponseError("Twitch returned an invalid response.") from None
    if not isinstance(payload, dict):
        raise TwitchResponseError("Twitch returned an invalid response.")
    return payload


def _data(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("data", [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise TwitchResponseError("Twitch returned invalid resource data.")
    return items


def _raise_helix_error(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise TwitchRateLimitError("Twitch API rate limit reached.")
    if response.status_code in {401, 403}:
        raise TwitchInvalidCredentialsError("Twitch credentials or token are invalid.")
    if response.status_code >= 500:
        raise TwitchUnavailableError("Twitch service is unavailable.")
    raise TwitchAdapterError("Twitch API request was rejected.")


def _parse_lookup(value: str) -> tuple[str, str] | None:
    candidate = value.strip()
    if not candidate or len(candidate) > 200 or re.search(r"[\x00-\x1f]", candidate):
        return None
    if candidate.startswith(("http://", "https://")):
        parts = urlsplit(candidate)
        if (parts.hostname or "").casefold() not in {"twitch.tv", "www.twitch.tv", "m.twitch.tv"}:
            return None
        segments = [segment for segment in parts.path.split("/") if segment]
        if len(segments) != 1:
            return None
        candidate = segments[0]
    candidate = candidate.lstrip("@").casefold()
    if candidate.isdigit():
        return "id", candidate
    if re.fullmatch(r"[a-z0-9_]{3,25}", candidate):
        return "login", candidate
    return None


def _profile_text(profile: NormalizedProfile) -> str:
    return " ".join(filter(None, [
        profile.username, profile.display_name, profile.biography,
        *profile.categories, *profile.keywords,
    ])).casefold()
