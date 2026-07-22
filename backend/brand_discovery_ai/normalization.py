"""Platform-payload normalization with strict validation and source attribution."""

from datetime import datetime, timezone
import hashlib
import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .discovery_schemas import NormalizedProfile, Platform


def safe_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.encode("idna").decode("ascii").lower()
    if host in {"localhost", "0.0.0.0", "::1"} or host.endswith(".local"):
        return None
    if re.fullmatch(r"127(?:\.\d{1,3}){3}", host):
        return None
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            return None
    except ValueError:
        pass
    netloc = host + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "", parts.query, ""))


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _rate(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100:
        return round(float(value), 4)
    return None


def normalize_payload(platform: Platform, payload: dict[str, Any], source: str) -> NormalizedProfile:
    warnings = list(payload.get("warnings") or [])
    profile_url = safe_url(payload.get("profile_url"))
    website = safe_url(payload.get("website"))
    if payload.get("profile_url") and not profile_url:
        warnings.append("Unsafe or invalid profile URL omitted.")
    if payload.get("website") and not website:
        warnings.append("Unsafe or invalid website URL omitted.")
    metrics = {}
    for field in ("follower_count", "following_count", "content_count", "total_view_count", "average_views", "average_likes", "average_comments"):
        metrics[field] = _count(payload.get(field))
        if payload.get(field) is not None and metrics[field] is None:
            warnings.append(f"Invalid {field} omitted.")
    engagement = _rate(payload.get("engagement_rate"))
    if payload.get("engagement_rate") is not None and engagement is None:
        warnings.append("Invalid engagement_rate omitted.")
    timestamp = payload.get("collected_at")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            timestamp = None
    if not isinstance(timestamp, datetime):
        timestamp = datetime.now(timezone.utc)
        warnings.append("Missing or invalid collection timestamp replaced at normalization time.")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    published_at = payload.get("published_at")
    if isinstance(published_at, str):
        try:
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError:
            published_at = None
            warnings.append("Invalid published_at omitted.")
    elif published_at is not None and not isinstance(published_at, datetime):
        published_at = None
        warnings.append("Invalid published_at omitted.")
    if isinstance(published_at, datetime) and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    email = payload.get("business_email")
    email_hash = hashlib.sha256(email.strip().casefold().encode()).hexdigest() if isinstance(email, str) and "@" in email else None
    return NormalizedProfile(
        entity_type=payload["entity_type"], platform=platform, platform_id=str(payload["id"]),
        username=payload.get("username"), display_name=payload.get("display_name"),
        profile_url=profile_url, biography=payload.get("biography"),
        categories=payload.get("categories") or [], keywords=payload.get("keywords") or [],
        location=payload.get("location"), language=payload.get("language"), **metrics,
        engagement_rate=engagement, verified=payload.get("verified"), website=website,
        business_email_available=payload.get("business_email_available"),
        business_email_hash=email_hash, linked_social_urls=[u for u in (safe_url(v) for v in payload.get("linked_social_urls") or []) if u],
        audience_demographics=payload.get("audience_demographics"), source=source,
        source_confidence=payload.get("source_confidence", 0.75), published_at=published_at,
        collected_at=timestamp,
        warnings=list(dict.fromkeys(warnings)),
    )


def deduplicate_profiles(profiles: list[NormalizedProfile]) -> list[NormalizedProfile]:
    """Remove source duplicates only; never merge identities across platforms."""
    unique = {}
    for profile in profiles:
        key = (profile.platform, profile.platform_id)
        current = unique.get(key)
        if current is None or profile.source_confidence > current.source_confidence:
            unique[key] = profile
    return list(unique.values())
