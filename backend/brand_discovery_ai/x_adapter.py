"""Official X API v2 SourceProvider using app-only bearer authentication."""

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from .discovery_schemas import AdapterCapabilities, DiscoveryCriteria, NormalizedProfile, Platform
from .normalization import normalize_payload, safe_url
from .source_adapters import SourceProvider
from .x_config import XSettings
from .x_errors import (
    XAccessRestrictedError, XAdapterError, XDisabledError, XInvalidTokenError,
    XMalformedRequestError, XNotFoundError, XRateLimitError, XResponseError,
    XTimeoutError, XUnavailableError, XUnsupportedCapabilityError,
)


X_API_BASE_URL = "https://api.x.com/2"
_USER_FIELDS = ",".join((
    "created_at", "description", "entities", "location", "profile_image_url",
    "protected", "public_metrics", "url", "verified", "verified_type",
))
_MAX_CACHE_ENTRIES = 256


class XApiAdapter(SourceProvider):
    platform = Platform.X

    def __init__(
        self,
        settings: XSettings,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        base_url: str = X_API_BASE_URL,
    ):
        self.settings = settings.validate()
        self._transport = http_transport
        self._base_url = base_url.rstrip("/")
        self._cache: OrderedDict[tuple[Any, ...], tuple[float, dict[str, Any]]] = OrderedDict()

    @property
    def capabilities(self) -> AdapterCapabilities:
        available = self.settings.enabled
        return AdapterCapabilities(
            keyword_search=available, category_search=False,
            username_lookup=available, location_filtering=False,
            follower_metrics=available, content_metrics=available,
            audience_demographics=False, brand_discovery=False,
            creator_discovery=available,
        )

    async def search_creators(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        if not self.settings.enabled:
            raise XDisabledError("X integration is disabled.")
        if not criteria.niche and not criteria.keywords:
            if criteria.categories:
                raise XUnsupportedCapabilityError("X category-only discovery is unsupported.")
            return []
        exact = _exact_lookup(criteria)
        if exact:
            profile = await self._lookup(exact, cache_namespace="search_exact")
            return [profile] if profile else []
        query = _search_query(criteria)
        maximum = min(self.settings.max_results, criteria.result_limit)
        payload = await self._request(
            "search", "users/search",
            {"query": query, "max_results": str(maximum), "user.fields": _USER_FIELDS},
        )
        profiles = [self._normalize(user) for user in _user_list(payload)]
        exclusions = {value.casefold() for value in criteria.exclusions}
        if exclusions:
            profiles = [
                profile for profile in profiles
                if not any(value in _profile_text(profile) for value in exclusions)
            ]
        return profiles

    async def search_brands(self, criteria: DiscoveryCriteria) -> list[NormalizedProfile]:
        del criteria
        return []

    async def get_profile(self, platform_id_or_username: str) -> NormalizedProfile | None:
        lookup = _parse_lookup(platform_id_or_username)
        if lookup is None:
            return None
        return await self._lookup(lookup, cache_namespace="profile")

    async def health_check(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "platform": "x", "network": False}
        return {"status": "configured", "platform": "x", "network": True}

    async def _lookup(
        self, lookup: tuple[str, str], *, cache_namespace: str,
    ) -> NormalizedProfile | None:
        field, value = lookup
        endpoint = f"users/{value}" if field == "id" else f"users/by/username/{value}"
        try:
            payload = await self._request(
                cache_namespace, endpoint, {"user.fields": _USER_FIELDS},
            )
        except XNotFoundError:
            return None
        data = payload.get("data")
        if data is None:
            return None
        if not isinstance(data, dict):
            raise XResponseError("X returned an invalid profile response.")
        return self._normalize(data)

    async def _request(
        self, cache_namespace: str, endpoint: str, params: dict[str, str],
    ) -> dict[str, Any]:
        if not self.settings.enabled:
            raise XDisabledError("X integration is disabled.")
        cache_key = (cache_namespace, endpoint, tuple(sorted(params.items())))
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        headers = {"Authorization": f"Bearer {self.settings.bearer_token}"}
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(
                    transport=self._transport,
                    timeout=httpx.Timeout(self.settings.timeout_seconds),
                ) as client:
                    response = await client.get(
                        f"{self._base_url}/{endpoint}", params=params, headers=headers,
                    )
            except httpx.TimeoutException:
                raise XTimeoutError("X request timed out.") from None
            except httpx.RequestError:
                raise XUnavailableError("X service is unavailable.") from None
            if response.status_code >= 500 and attempt == 0:
                continue
            if response.status_code >= 400:
                _raise_api_error(response.status_code)
            payload = _json_object(response)
            self._cache_put(cache_key, payload)
            return payload
        raise XUnavailableError("X service is unavailable.")

    def _cache_get(self, key: tuple[Any, ...]) -> dict[str, Any] | None:
        cached = self._cache.get(key)
        if cached is None:
            return None
        if cached[0] <= time.monotonic():
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return deepcopy(cached[1])

    def _cache_put(self, key: tuple[Any, ...], payload: dict[str, Any]) -> None:
        self._cache[key] = (
            time.monotonic() + self.settings.cache_ttl_seconds, deepcopy(payload),
        )
        self._cache.move_to_end(key)
        while len(self._cache) > _MAX_CACHE_ENTRIES:
            self._cache.popitem(last=False)

    def _normalize(self, user: dict[str, Any]) -> NormalizedProfile:
        user_id = user.get("id")
        username = user.get("username")
        if not isinstance(user_id, str) or not re.fullmatch(r"[0-9]{1,19}", user_id):
            raise XResponseError("X profile response omitted a valid user ID.")
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,15}", username):
            raise XResponseError("X profile response omitted a valid username.")
        metrics = user.get("public_metrics")
        if metrics is not None and not isinstance(metrics, dict):
            raise XResponseError("X returned invalid public metrics.")
        metrics = metrics or {}
        verified = user.get("verified") if isinstance(user.get("verified"), bool) else None
        warnings = [
            "Entity type reflects creator discovery context; X does not classify accounts as creators or brands.",
            "X does not provide engagement rate, audience demographics, language, or business-email availability here.",
            "X profile image was omitted because the current shared profile contract has no backward-compatible image field.",
        ]
        if "verified" not in user:
            warnings.append("Verification status was not returned by the configured X API access tier.")
        if user.get("protected") is True:
            warnings.append("This X account is protected; public data may be limited.")
        payload = {
            "id": user_id, "entity_type": "creator", "username": username,
            "display_name": user.get("name"),
            "profile_url": f"https://x.com/{username}",
            "biography": user.get("description"), "categories": [], "keywords": [],
            "location": user.get("location"), "language": None,
            "follower_count": metrics.get("followers_count"),
            "following_count": metrics.get("following_count"),
            "content_count": metrics.get("tweet_count"),
            "total_view_count": None, "average_views": None, "average_likes": None,
            "average_comments": None, "engagement_rate": None,
            "verified": verified, "website": _website(user),
            "business_email_available": None, "audience_demographics": None,
            "published_at": user.get("created_at"), "source_confidence": 0.98,
            "collected_at": datetime.now(timezone.utc), "warnings": warnings,
        }
        return normalize_payload(Platform.X, payload, "x_api_v2")


def _json_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        raise XResponseError("X returned an invalid response.") from None
    if not isinstance(payload, dict):
        raise XResponseError("X returned an invalid response.")
    return payload


def _user_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", [])
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise XResponseError("X returned invalid user search data.")
    return data


def _raise_api_error(status_code: int) -> None:
    if status_code == 400:
        raise XMalformedRequestError("X rejected the request as malformed.")
    if status_code == 401:
        raise XInvalidTokenError("X bearer token is invalid or revoked.")
    if status_code == 403:
        raise XAccessRestrictedError("The configured X API access does not permit this operation.")
    if status_code == 404:
        raise XNotFoundError("X profile was not found.")
    if status_code == 429:
        raise XRateLimitError("X API rate limit reached.")
    if status_code >= 500:
        raise XUnavailableError("X service is unavailable.")
    raise XAdapterError("X API request was rejected.")


def _parse_lookup(value: str) -> tuple[str, str] | None:
    candidate = value.strip()
    if not candidate or len(candidate) > 200 or re.search(r"[\x00-\x1f\x7f]", candidate):
        return None
    if candidate.startswith(("http://", "https://")):
        try:
            parts = urlsplit(candidate)
        except ValueError:
            return None
        if (parts.hostname or "").casefold() not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
            return None
        segments = [segment for segment in parts.path.split("/") if segment]
        if len(segments) != 1:
            return None
        candidate = segments[0]
    candidate = candidate.lstrip("@")
    if re.fullmatch(r"[0-9]{1,19}", candidate):
        return "id", candidate
    if re.fullmatch(r"[A-Za-z0-9_]{1,15}", candidate):
        return "username", candidate.casefold()
    return None


def _exact_lookup(criteria: DiscoveryCriteria) -> tuple[str, str] | None:
    terms = [value for value in [criteria.niche, *criteria.keywords] if value]
    if len(terms) != 1:
        return None
    term = terms[0].strip()
    if not (term.startswith("@") or term.startswith(("https://x.com/", "https://www.x.com/", "https://twitter.com/", "https://www.twitter.com/"))):
        return None
    return _parse_lookup(term)


def _search_query(criteria: DiscoveryCriteria) -> str:
    query = " ".join(value for value in [criteria.niche, *criteria.keywords] if value)
    query = re.sub(r"\s+", " ", query).strip()
    if not re.fullmatch(r"[A-Za-z0-9_' ]{1,50}", query):
        raise XMalformedRequestError("X creator search query is invalid or unsupported.")
    return query


def _website(user: dict[str, Any]) -> str | None:
    entities = user.get("entities")
    if isinstance(entities, dict):
        url_entity = entities.get("url")
        urls = url_entity.get("urls") if isinstance(url_entity, dict) else None
        if isinstance(urls, list):
            for item in urls:
                if isinstance(item, dict):
                    candidate = safe_url(item.get("expanded_url"))
                    if candidate:
                        return candidate
    return safe_url(user.get("url"))


def _profile_text(profile: NormalizedProfile) -> str:
    return " ".join(filter(None, [
        profile.username, profile.display_name, profile.biography, profile.location,
    ])).casefold()
