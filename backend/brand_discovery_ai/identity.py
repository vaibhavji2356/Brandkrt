"""Conservative, non-persistent cross-platform identity suggestions."""

from pydantic import BaseModel, Field

from .discovery_schemas import NormalizedProfile


class IdentitySuggestion(BaseModel):
    left_platform_id: str
    right_platform_id: str
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    automatic_merge_allowed: bool


def suggest_identity(left: NormalizedProfile, right: NormalizedProfile) -> IdentitySuggestion:
    reasons, scores = [], []
    if left.entity_type != right.entity_type:
        return _suggestion(left, right, 0, ["Entity types differ."])
    if left.platform == right.platform:
        return _suggestion(left, right, 0, ["Cross-platform linking requires different platforms."])
    if left.website and right.website and left.website.casefold() == right.website.casefold():
        reasons.append("Exact verified website URL.")
        scores.append(1.0)
    linked_left = {url.casefold() for url in left.linked_social_urls}
    linked_right = {url.casefold() for url in right.linked_social_urls}
    if linked_left & linked_right or (left.profile_url and left.profile_url.casefold() in linked_right) or (right.profile_url and right.profile_url.casefold() in linked_left):
        reasons.append("Exact linked social URL.")
        scores.append(0.97)
    if left.business_email_hash and left.business_email_hash == right.business_email_hash:
        reasons.append("Exact normalized business email hash.")
        scores.append(0.99)
    if left.username and right.username and left.username.lstrip("@").casefold() == right.username.lstrip("@").casefold():
        reasons.append("Exact normalized username.")
        scores.append(0.70)
    confidence = max(scores, default=0.0)
    return _suggestion(left, right, confidence, reasons or ["No permitted exact identity signals matched."])


def _suggestion(left, right, confidence, reasons):
    return IdentitySuggestion(
        left_platform_id=f"{left.platform.value}:{left.platform_id}",
        right_platform_id=f"{right.platform.value}:{right.platform_id}",
        confidence=confidence, reasons=reasons,
        automatic_merge_allowed=confidence >= 0.95,
    )
