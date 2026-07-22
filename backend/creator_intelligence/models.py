"""Additive contracts for pricing, ROI, and creator portfolio intelligence."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from research_agent.models import ResearchPackage


ShortText = Annotated[str, StringConstraints(min_length=1, max_length=500)]


class CampaignObjective(str, Enum):
    AWARENESS = "Brand Awareness"
    APP_INSTALL = "App Install"
    SALES = "Sales"
    GAMING_LAUNCH = "Gaming Launch"
    PRODUCT_REVIEW = "Product Review"


class PriceRange(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    minimum: float = Field(ge=0, le=1_000_000_000)
    maximum: float = Field(ge=0, le=1_000_000_000)

    @model_validator(mode="after")
    def range_is_ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


class PricingHistoryEntry(BaseModel):
    """Non-persistent hook for caller-supplied negotiation history."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    amount: float = Field(ge=0, le=1_000_000_000)
    status: str = Field(min_length=1, max_length=50)
    note: str | None = Field(default=None, max_length=500)


class CreatorPricingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    known_rate: float | None = Field(default=None, ge=0, le=1_000_000_000)
    known_rate_verified: bool = False
    estimated_rate: float | None = Field(default=None, ge=0, le=1_000_000_000)
    negotiated_rate: float | None = Field(default=None, ge=0, le=1_000_000_000)
    negotiated_rate_verified: bool = False
    manual_rate_override: float | None = Field(default=None, ge=0, le=1_000_000_000)
    price_range: PriceRange | None = None
    price_confidence: float | None = Field(default=None, ge=0, le=1)
    pricing_source: str | None = Field(default=None, max_length=120)
    pricing_notes: list[str] = Field(default_factory=list, max_length=20)
    history: list[PricingHistoryEntry] = Field(default_factory=list, max_length=30)


class CreatorInsightInput(BaseModel):
    """Optional legitimate observations supplied outside the platform profile."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    profile_reference: str = Field(min_length=3, max_length=300)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    pricing: CreatorPricingInput | None = None
    average_views: int | None = Field(default=None, ge=0)
    average_likes: int | None = Field(default=None, ge=0)
    average_comments: int | None = Field(default=None, ge=0)
    posting_frequency: float | None = Field(default=None, ge=0, le=1000)
    audience_quality_score: float | None = Field(default=None, ge=0, le=100)
    content_quality_score: float | None = Field(default=None, ge=0, le=100)


class CreatorIntelligenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    research_package: ResearchPackage
    campaign_budget: float = Field(gt=0, le=1_000_000_000)
    number_of_creators: int = Field(default=3, ge=1, le=10)
    minimum_reach: int | None = Field(default=None, ge=0)
    campaign_objective: CampaignObjective
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    creator_inputs: list[CreatorInsightInput] = Field(default_factory=list, max_length=50)
    include_ai_narrative: bool = False
    use_commercial_history: bool = False

    @field_validator("creator_inputs")
    @classmethod
    def creator_inputs_are_unique(cls, values: list[CreatorInsightInput]) -> list[CreatorInsightInput]:
        keys = [item.profile_reference.casefold() for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("creator_inputs must have unique profile_reference values")
        return values

    @model_validator(mode="after")
    def creator_currencies_match_campaign(self):
        mismatches = [item.profile_reference for item in self.creator_inputs if item.currency and item.currency != self.currency]
        if mismatches:
            raise ValueError("creator input currency must match campaign currency")
        return self


class PricingAnalysis(BaseModel):
    profile_reference: str
    selected_rate: float | None = Field(default=None, ge=0)
    estimated_rate: float | None = Field(default=None, ge=0)
    negotiated_rate: float | None = Field(default=None, ge=0)
    currency: str
    rate_type: str | None = None
    expected_negotiation_range: PriceRange | None = None
    price_confidence: float = Field(ge=0, le=1)
    pricing_source: str | None = None
    manual_override_applied: bool = False
    verified_rate_preserved: bool = False
    pricing_notes: list[str] = Field(default_factory=list)


class CreatorMetrics(BaseModel):
    profile_reference: str
    estimated_rate: float | None = Field(default=None, ge=0)
    negotiated_rate: float | None = Field(default=None, ge=0)
    currency: str
    price_confidence: float = Field(ge=0, le=1)
    engagement_rate: float | None = Field(default=None, ge=0, le=100)
    average_views: int | None = Field(default=None, ge=0)
    average_likes: int | None = Field(default=None, ge=0)
    average_comments: int | None = Field(default=None, ge=0)
    posting_frequency: float | None = Field(default=None, ge=0)
    audience_quality_score: float | None = Field(default=None, ge=0, le=100)
    creator_quality_score: float | None = Field(default=None, ge=0, le=100)
    cost_per_engagement: float | None = Field(default=None, ge=0)
    cpm_reach: float | None = Field(default=None, ge=0)
    roi_score: float | None = Field(default=None, ge=0, le=100)
    budget_fit_score: float | None = Field(default=None, ge=0, le=100)
    recommendation_score: float | None = Field(default=None, ge=0, le=100)
    pricing_notes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ROIAnalysis(BaseModel):
    profile_reference: str | None = None
    expected_reach: int | None = Field(default=None, ge=0)
    expected_engagements: int | None = Field(default=None, ge=0)
    cost_per_engagement: float | None = Field(default=None, ge=0)
    cpm_reach: float | None = Field(default=None, ge=0)
    roi_score: float | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class RecommendationExplanation(BaseModel):
    why_recommended: list[ShortText]
    strengths: list[ShortText]
    weaknesses: list[ShortText]
    pricing_concerns: list[ShortText]
    budget_fit: ShortText
    risks: list[ShortText]


class RecommendedCreator(BaseModel):
    profile_reference: str
    platform: str
    username: str | None = None
    selected: bool
    rank: int = Field(ge=1)
    metrics: CreatorMetrics
    pricing: PricingAnalysis
    roi: ROIAnalysis
    explanation: RecommendationExplanation
    warnings: list[str] = Field(default_factory=list)


class BudgetAnalysis(BaseModel):
    campaign_budget: float = Field(gt=0)
    expected_spend: float = Field(ge=0)
    remaining_budget: float = Field(ge=0)
    budget_utilization: float = Field(ge=0, le=100)
    selected_creator_count: int = Field(ge=0)
    requested_creator_count: int = Field(ge=1)
    expected_reach: int | None = Field(default=None, ge=0)
    expected_engagements: int | None = Field(default=None, ge=0)
    minimum_reach_met: bool | None = None
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class CreatorIntelligenceResponse(BaseModel):
    recommendations: list[RecommendedCreator]
    ranking: list[str]
    pricing_analysis: list[PricingAnalysis]
    budget_analysis: BudgetAnalysis
    roi_analysis: ROIAnalysis
    confidence: float = Field(ge=0, le=1)
    reasoning_source: str
    warnings: list[str] = Field(default_factory=list)
    ai_narrative: "PortfolioNarrative | None" = None
    narrative_source: Literal["disabled", "openai_grounded", "deterministic_fallback"] = "disabled"
    narrative_degraded: bool = False


class CreatorNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_reference: str = Field(min_length=3, max_length=300)
    platform: str = Field(min_length=1, max_length=40)
    platform_id: str = Field(min_length=1, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    selection_reason: ShortText
    strengths: list[ShortText] = Field(min_length=1, max_length=5)
    weaknesses: list[ShortText] = Field(min_length=1, max_length=5)
    pricing_assessment: ShortText
    negotiation_guidance: ShortText
    uncertainty: ShortText
    risk_flags: list[ShortText] = Field(min_length=1, max_length=5)


class PortfolioNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executive_summary: ShortText
    objective_alignment: ShortText
    budget_assessment: ShortText
    portfolio_tradeoffs: list[ShortText] = Field(min_length=1, max_length=5)
    expected_efficiency_summary: ShortText
    risk_summary: list[ShortText] = Field(min_length=1, max_length=5)
    recommended_actions: list[ShortText] = Field(min_length=1, max_length=5)
    creator_narratives: list[CreatorNarrative] = Field(max_length=50)
    confidence_statement: ShortText
    warnings: list[ShortText] = Field(max_length=10)
