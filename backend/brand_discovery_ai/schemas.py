"""Strict request and response contracts for Brand Discovery preview."""

from typing import Annotated, Optional
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=120)]
ReasonText = Annotated[str, StringConstraints(min_length=1, max_length=300)]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class BrandDiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    industry: Optional[str] = Field(default=None, max_length=100)
    niche: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=120)
    target_audience: Optional[str] = Field(default=None, max_length=500)
    campaign_objective: Optional[str] = Field(default=None, max_length=500)
    minimum_budget: Optional[float] = Field(default=None, ge=0, le=1_000_000_000)
    maximum_budget: Optional[float] = Field(default=None, ge=0, le=1_000_000_000)
    preferred_platforms: Optional[list[Annotated[str, StringConstraints(min_length=1, max_length=50)]]] = Field(
        default=None, max_length=8
    )
    brand_size: Optional[str] = Field(default=None, max_length=50)
    keywords: Optional[list[Annotated[str, StringConstraints(min_length=1, max_length=80)]]] = Field(
        default=None, max_length=15
    )
    exclusions: Optional[list[Annotated[str, StringConstraints(min_length=1, max_length=120)]]] = Field(
        default=None, max_length=15
    )
    result_limit: int = Field(default=5, ge=1, le=20)

    @field_validator(
        "industry",
        "niche",
        "location",
        "target_audience",
        "campaign_objective",
        "brand_size",
        mode="before",
    )
    @classmethod
    def normalize_scalar_text(cls, value):
        if value is None or not isinstance(value, str):
            return value
        normalized = _normalize_text(value)
        return normalized or None

    @field_validator("preferred_platforms", "keywords", "exclusions", mode="before")
    @classmethod
    def normalize_text_lists(cls, value, info):
        if value is None:
            return None
        if not isinstance(value, list):
            return value
        limits = {"preferred_platforms": 8, "keywords": 15, "exclusions": 15}
        if len(value) > limits[info.field_name]:
            raise ValueError("Too many list items")

        normalized_items = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("List items must be strings")
            normalized = _normalize_text(item)
            if not normalized:
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key not in seen:
                seen.add(dedupe_key)
                normalized_items.append(normalized)
        return normalized_items or None

    @model_validator(mode="after")
    def validate_request(self):
        if (
            self.minimum_budget is not None
            and self.maximum_budget is not None
            and self.minimum_budget > self.maximum_budget
        ):
            raise ValueError("minimum_budget must not exceed maximum_budget")

        criteria = self.model_dump(exclude={"result_limit"}, exclude_none=True)
        if not criteria:
            raise ValueError("At least one discovery criterion is required")
        return self


class BrandDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)

    brand_name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    website: Optional[HttpUrl] = None
    industry: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    description: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    location: Optional[Annotated[str, StringConstraints(min_length=1, max_length=120)]] = None
    relevance_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    fit_reasons: list[ReasonText] = Field(min_length=1, max_length=8)
    outreach_angle: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    source_type: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    warnings: list[ReasonText] = Field(default_factory=list, max_length=8)


class ProviderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[BrandDiscoveryResult] = Field(min_length=1, max_length=20)


class BrandDiscoveryPreviewResponse(BaseModel):
    results: list[BrandDiscoveryResult] = Field(max_length=20)
    count: int = Field(ge=0, le=20)
    provider: Annotated[str, StringConstraints(min_length=1, max_length=50)]
    mock_mode: bool

