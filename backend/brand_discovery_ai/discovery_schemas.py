"""Normalized contracts for factual, multi-platform discovery."""

from datetime import datetime
from enum import Enum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EntityType(str, Enum):
    CREATOR = "creator"
    BRAND = "brand"
    BOTH = "both"


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    SNAPCHAT = "snapchat"
    TWITCH = "twitch"
    X = "x"


class AudienceDemographics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    age_ranges: dict[str, float] | None = None
    genders: dict[str, float] | None = None
    top_locations: dict[str, float] | None = None


class NormalizedProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    entity_type: Literal["creator", "brand"]
    platform: Platform
    platform_id: str = Field(min_length=1, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    profile_url: str | None = None
    biography: str | None = Field(default=None, max_length=2000)
    categories: list[str] = Field(default_factory=list, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default=None, max_length=35)
    follower_count: int | None = Field(default=None, ge=0)
    following_count: int | None = Field(default=None, ge=0)
    content_count: int | None = Field(default=None, ge=0)
    total_view_count: int | None = Field(default=None, ge=0)
    average_views: int | None = Field(default=None, ge=0)
    average_likes: int | None = Field(default=None, ge=0)
    average_comments: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0, le=100)
    verified: bool | None = None
    website: str | None = None
    business_email_available: bool | None = None
    business_email_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    linked_social_urls: list[str] = Field(default_factory=list, max_length=20)
    audience_demographics: AudienceDemographics | None = None
    source: str = Field(min_length=1, max_length=100)
    source_confidence: float = Field(ge=0, le=1)
    published_at: datetime | None = None
    collected_at: datetime
    warnings: list[str] = Field(default_factory=list, max_length=30)


class DiscoveryCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    entity_type: EntityType = EntityType.BOTH
    platforms: list[Platform] = Field(default_factory=lambda: list(Platform), min_length=1, max_length=5)
    niche: str | None = Field(default=None, max_length=120)
    categories: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    location: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=35)
    minimum_followers: int | None = Field(default=None, ge=0)
    maximum_followers: int | None = Field(default=None, ge=0)
    minimum_engagement_rate: float | None = Field(default=None, ge=0, le=100)
    campaign_objective: str | None = Field(default=None, max_length=500)
    minimum_budget: float | None = Field(default=None, ge=0, le=1_000_000_000)
    maximum_budget: float | None = Field(default=None, ge=0, le=1_000_000_000)
    result_limit: int = Field(default=10, ge=1, le=50)

    @field_validator("categories", "keywords", "exclusions", mode="before")
    @classmethod
    def clean_lists(cls, value: Any):
        if not isinstance(value, list):
            return value
        result, seen = [], set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")
            cleaned = re.sub(r"\s+", " ", item).strip()
            if cleaned and cleaned.casefold() not in seen:
                seen.add(cleaned.casefold())
                result.append(cleaned)
        return result

    @model_validator(mode="after")
    def ranges_are_ordered(self):
        if self.minimum_followers is not None and self.maximum_followers is not None:
            if self.minimum_followers > self.maximum_followers:
                raise ValueError("minimum_followers must not exceed maximum_followers")
        if self.minimum_budget is not None and self.maximum_budget is not None:
            if self.minimum_budget > self.maximum_budget:
                raise ValueError("minimum_budget must not exceed maximum_budget")
        return self


class AdapterCapabilities(BaseModel):
    keyword_search: bool
    category_search: bool
    username_lookup: bool
    location_filtering: bool
    follower_metrics: bool
    content_metrics: bool
    audience_demographics: bool
    brand_discovery: bool
    creator_discovery: bool


class RankingBreakdown(BaseModel):
    category_relevance: float
    keyword_relevance: float
    location_match: float | None
    language_match: float | None
    platform_preference: float
    follower_range_match: float | None
    engagement_match: float | None
    data_completeness: float
    source_confidence: float


class RankedProfile(BaseModel):
    profile: NormalizedProfile
    score: float = Field(ge=0, le=100)
    score_components: RankingBreakdown
    warnings: list[str] = Field(default_factory=list)


class DiscoveryPreviewResponse(BaseModel):
    results: list[RankedProfile]
    count: int
    mock_mode: Literal[True] = True
    sources: list[str]
    warnings: list[str] = Field(default_factory=list)
