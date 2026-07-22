"""Strict public contracts for commercial records and read-only analytics."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from brand_discovery_ai.discovery_schemas import Platform
from creator_intelligence.models import CampaignObjective


Note = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Money = Annotated[float, Field(ge=0, le=1_000_000_000, allow_inf_nan=False)]


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class RateType(str, Enum):
    KNOWN = "known"
    NEGOTIATED = "negotiated"
    ESTIMATED = "estimated"
    RANGE = "range"


class NegotiationStatus(str, Enum):
    QUOTED = "quoted"
    COUNTERED = "countered"
    AGREED = "agreed"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("timestamp must be timezone-aware")
    return value


class CommercialProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    platform: Platform
    platform_id: str = Field(min_length=1, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    currency: Currency
    current_known_rate: Money | None = None
    current_negotiated_rate: Money | None = None
    rate_verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    pricing_notes: list[Note] = Field(default_factory=list, max_length=20)
    internal_notes: list[Note] = Field(default_factory=list, max_length=20)


class CommercialProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    username: str | None = Field(default=None, max_length=200)
    pricing_notes: list[Note] | None = Field(default=None, max_length=20)
    internal_notes: list[Note] | None = Field(default=None, max_length=20)
    correction_reason: Note | None = None


class CommercialProfile(BaseModel):
    id: str
    platform: Platform
    platform_id: str
    username: str | None = None
    currency: Currency
    current_known_rate: Money | None = None
    current_negotiated_rate: Money | None = None
    rate_verification_status: VerificationStatus
    pricing_notes: list[str]
    created_at: datetime
    updated_at: datetime


class RateHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    rate_type: RateType
    amount: Money | None = None
    currency: Currency
    min_amount: Money | None = None
    max_amount: Money | None = None
    source: str = Field(min_length=1, max_length=120)
    verification_status: VerificationStatus
    effective_at: datetime
    notes: list[Note] = Field(default_factory=list, max_length=20)
    internal_notes: list[Note] = Field(default_factory=list, max_length=20)

    _effective_utc = field_validator("effective_at")(_aware_utc)

    @model_validator(mode="after")
    def valid_amount_shape(self):
        if self.rate_type == RateType.RANGE:
            if self.min_amount is None or self.max_amount is None:
                raise ValueError("range rates require min_amount and max_amount")
            if self.min_amount > self.max_amount:
                raise ValueError("min_amount must not exceed max_amount")
        elif self.amount is None:
            raise ValueError("non-range rates require amount")
        return self


class RateHistoryRecord(RateHistoryCreate):
    internal_notes: list[Note] = Field(default_factory=list, exclude=True)
    id: str
    commercial_profile_id: str
    created_at: datetime


class NegotiationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    campaign_id: str | None = Field(default=None, max_length=100)
    initially_quoted_amount: Money | None = None
    counter_offer_amount: Money | None = None
    agreed_amount: Money | None = None
    currency: Currency
    status: NegotiationStatus
    notes: list[Note] = Field(default_factory=list, max_length=20)
    internal_notes: list[Note] = Field(default_factory=list, max_length=20)
    occurred_at: datetime

    _occurred_utc = field_validator("occurred_at")(_aware_utc)

    @model_validator(mode="after")
    def status_has_amount(self):
        if not any(value is not None for value in (
            self.initially_quoted_amount, self.counter_offer_amount, self.agreed_amount,
        )):
            raise ValueError("at least one negotiation amount is required")
        if self.status == NegotiationStatus.AGREED and self.agreed_amount is None:
            raise ValueError("agreed status requires agreed_amount")
        return self


class NegotiationRecord(NegotiationCreate):
    internal_notes: list[Note] = Field(default_factory=list, exclude=True)
    id: str
    commercial_profile_id: str
    created_at: datetime


class CampaignPerformanceBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    campaign_id: str = Field(min_length=1, max_length=100)
    commercial_profile_id: str = Field(min_length=1, max_length=100)
    objective: CampaignObjective
    agreed_cost: Money
    currency: Currency
    deliverable_type: str = Field(min_length=1, max_length=100)
    deliverables_committed: int | None = Field(default=None, ge=0, le=100_000)
    deliverables_completed: int | None = Field(default=None, ge=0, le=100_000)
    observed_reach: int | None = Field(default=None, ge=0)
    observed_views: int | None = Field(default=None, ge=0)
    observed_impressions: int | None = Field(default=None, ge=0)
    observed_likes: int | None = Field(default=None, ge=0)
    observed_comments: int | None = Field(default=None, ge=0)
    observed_shares: int | None = Field(default=None, ge=0)
    observed_clicks: int | None = Field(default=None, ge=0)
    observed_conversions: int | None = Field(default=None, ge=0)
    revenue: Money | None = None
    evidence_status: VerificationStatus
    measurement_source: str = Field(min_length=1, max_length=200)
    measurement_period_start: datetime
    measurement_period_end: datetime
    notes: list[Note] = Field(default_factory=list, max_length=20)
    internal_notes: list[Note] = Field(default_factory=list, max_length=20)
    estimated_spend: Money | None = None
    estimated_reach: int | None = Field(default=None, ge=0)
    estimated_engagements: int | None = Field(default=None, ge=0)
    estimated_cpe: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    estimated_cpm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    creator_quality_score_at_selection: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    _period_start_utc = field_validator("measurement_period_start")(_aware_utc)
    _period_end_utc = field_validator("measurement_period_end")(_aware_utc)

    @model_validator(mode="after")
    def period_is_valid(self):
        if self.measurement_period_start > self.measurement_period_end:
            raise ValueError("measurement_period_start must not exceed measurement_period_end")
        return self


class CampaignPerformanceCreate(CampaignPerformanceBase):
    pass


class CampaignPerformancePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    agreed_cost: Money | None = None
    deliverables_committed: int | None = Field(default=None, ge=0, le=100_000)
    deliverables_completed: int | None = Field(default=None, ge=0, le=100_000)
    observed_reach: int | None = Field(default=None, ge=0)
    observed_views: int | None = Field(default=None, ge=0)
    observed_impressions: int | None = Field(default=None, ge=0)
    observed_likes: int | None = Field(default=None, ge=0)
    observed_comments: int | None = Field(default=None, ge=0)
    observed_shares: int | None = Field(default=None, ge=0)
    observed_clicks: int | None = Field(default=None, ge=0)
    observed_conversions: int | None = Field(default=None, ge=0)
    revenue: Money | None = None
    evidence_status: VerificationStatus | None = None
    measurement_source: str | None = Field(default=None, min_length=1, max_length=200)
    measurement_period_start: datetime | None = None
    measurement_period_end: datetime | None = None
    notes: list[Note] | None = Field(default=None, max_length=20)
    internal_notes: list[Note] | None = Field(default=None, max_length=20)
    estimated_spend: Money | None = None
    estimated_reach: int | None = Field(default=None, ge=0)
    estimated_engagements: int | None = Field(default=None, ge=0)
    estimated_cpe: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    estimated_cpm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    creator_quality_score_at_selection: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    correction_reason: Note | None = None

    _period_start_utc = field_validator("measurement_period_start")(_aware_utc)
    _period_end_utc = field_validator("measurement_period_end")(_aware_utc)

    @model_validator(mode="after")
    def required_fields_cannot_be_cleared(self):
        for field in ("agreed_cost", "evidence_status", "measurement_source", "measurement_period_start", "measurement_period_end"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CampaignPerformanceRecord(CampaignPerformanceBase):
    internal_notes: list[Note] = Field(default_factory=list, exclude=True)
    id: str
    platform: Platform
    platform_id: str
    username: str | None = None
    version: int = Field(default=1, ge=1)
    warnings: list[str] = Field(default_factory=list)
    metric_evidence: list["MetricEvidenceStatus"] = Field(default_factory=list)
    evidence_confidence: float = Field(default=0, ge=0, le=1)
    created_at: datetime
    updated_at: datetime


class MetricComparison(BaseModel):
    estimate: float | int | None = None
    observed: float | int | None = None
    variance: float | None = None
    estimate_status: Literal["estimate", "unavailable"]
    observed_status: Literal["verified", "unverified", "unavailable"]


class PerformanceComparison(BaseModel):
    performance_record_id: str
    currency: Currency
    spend: MetricComparison
    reach: MetricComparison
    engagements: MetricComparison
    cpe: MetricComparison
    cpm: MetricComparison
    deliverables: MetricComparison
    creator_quality_score_at_selection: float | None = Field(default=None, ge=0, le=100)
    observed_campaign_efficiency_score: float | None = Field(default=None, ge=0, le=100)
    evidence_confidence: float = Field(default=0, ge=0, le=1)
    evidence_summary: list["MetricEvidenceStatus"] = Field(default_factory=list)
    methodology: str
    warnings: list[str]


class MetricEvidenceStatus(BaseModel):
    metric: str = Field(min_length=1, max_length=80)
    observation_status: Literal["verified", "unverified", "unavailable"]
    evidence_status: Literal["verified", "unverified", "missing", "rejected", "deleted"]
    supporting_evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    verification_level: Literal["reviewed", "reviewed_limited", "unreviewed", "none"]
    confidence_note: str = Field(min_length=1, max_length=300)


class AnalyticsSummary(BaseModel):
    currency: Currency | None = None
    sample_sizes: dict[str, int]
    rate_trend: list[dict[str, str | float | None]]
    average_negotiated_discount_percent: float | None = None
    quoted_vs_agreed: dict[str, float | int | None]
    campaign_spend_by_creator: dict[str, float]
    campaign_spend_by_platform: dict[str, float]
    observed_cpe: float | None = None
    observed_cpm: float | None = None
    deliverable_completion_rate: float | None = None
    creator_repeat_collaboration_count: dict[str, int]
    average_reach_variance_percent: float | None = None
    low_evidence_record_count: int = Field(ge=0)
    missing_performance_record_count: int = Field(ge=0)
    evidence_notes: list[str]
