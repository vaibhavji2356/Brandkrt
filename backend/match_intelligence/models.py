"""Strict qualitative outputs for match intelligence."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


ConciseText = Annotated[str, StringConstraints(min_length=1, max_length=500)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=240)]


class RecommendationCategory(str, Enum):
    EXCELLENT = "Excellent Match"
    STRONG = "Strong Match"
    POSSIBLE = "Possible Match"
    WEAK = "Weak Match"


class CampaignType(str, Enum):
    PRODUCT_LAUNCH = "Product Launch"
    AWARENESS = "Awareness"
    UGC = "UGC"
    GIVEAWAY = "Giveaway"
    AFFILIATE = "Affiliate"
    REVIEW = "Review"
    BRAND_AMBASSADOR = "Brand Ambassador"
    SEASONAL = "Seasonal Campaign"


class ContentStyle(str, Enum):
    SHORTS = "Shorts"
    LONG_FORM = "Long-form"
    TUTORIAL = "Tutorial"
    REVIEW = "Review"
    LIFESTYLE = "Lifestyle"
    COMEDY = "Comedy"
    EDUCATIONAL = "Educational"


class CampaignStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_type: CampaignType
    campaign_goal: ConciseText
    content_style: ContentStyle


class OutreachPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_contact_angle: ConciseText
    collaboration_pitch: ConciseText
    value_proposition: ConciseText
    call_to_action: ConciseText


class MarketingIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_audience_overlap: ConciseText
    brand_positioning_compatibility: ConciseText
    expected_campaign_style: ConciseText
    estimated_collaboration_quality: ConciseText
    long_term_partnership_potential: ConciseText


class RecommendationRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    risk_type: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    explanation: ShortText


class CreatorRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_reference: Annotated[str, StringConstraints(min_length=3, max_length=300)]
    overall_match_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0, le=100)
    recommendation_category: RecommendationCategory
    recommendation_summary: ConciseText
    why_recommended: list[ShortText] = Field(min_length=1, max_length=5)
    strengths: list[ShortText] = Field(min_length=1, max_length=5)
    weaknesses: list[ShortText] = Field(min_length=1, max_length=5)
    campaign_fit: ConciseText
    audience_fit: ConciseText
    niche_fit: ConciseText
    budget_fit: ConciseText
    platform_fit: ConciseText
    marketing_intelligence: MarketingIntelligence
    campaign_strategy: CampaignStrategy
    outreach: OutreachPlan
    risks: list[RecommendationRisk] = Field(min_length=1, max_length=8)

    @field_validator("why_recommended", "strengths", "weaknesses")
    @classmethod
    def unique_list_items(cls, values):
        result, seen = [], set()
        for value in values:
            key = value.casefold().strip()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result


class MatchIntelligenceResponse(BaseModel):
    recommendations: list[CreatorRecommendation]
    count: int = Field(ge=0)
    degraded: bool
    reasoning_source: str
    warnings: list[str] = Field(default_factory=list)


class ProviderRecommendation(BaseModel):
    """Qualitative provider payload; authoritative scores never come from AI."""

    model_config = ConfigDict(extra="forbid")
    profile_reference: str
    ai_confidence: float = Field(ge=0, le=100)
    recommendation_summary: ConciseText
    why_recommended: list[ShortText] = Field(min_length=1, max_length=5)
    strengths: list[ShortText] = Field(min_length=1, max_length=5)
    weaknesses: list[ShortText] = Field(min_length=1, max_length=5)
    campaign_fit: ConciseText
    audience_fit: ConciseText
    niche_fit: ConciseText
    budget_fit: ConciseText
    platform_fit: ConciseText
    marketing_intelligence: MarketingIntelligence
    campaign_strategy: CampaignStrategy
    outreach: OutreachPlan
    risks: list[RecommendationRisk] = Field(min_length=1, max_length=8)


class ProviderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendations: list[ProviderRecommendation]
