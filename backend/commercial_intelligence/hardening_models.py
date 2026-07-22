"""Evidence, correction, retention, export, and audit review contracts."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .models import Currency, Money, Note, VerificationStatus, _aware_utc


InternalNote = Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class EvidenceType(str, Enum):
    ANALYTICS_SCREENSHOT = "analytics_screenshot"
    PLATFORM_EXPORT = "platform_export"
    INVOICE_COPY = "invoice_copy"
    SIGNED_RATE_CARD = "signed_rate_card"
    CONTRACT_REFERENCE = "contract_reference"
    DELIVERABLE_PROOF = "deliverable_proof"
    CAMPAIGN_REPORT = "campaign_report"
    PAYMENT_REFERENCE = "payment_reference"
    OTHER = "other"


class EvidenceSourceType(str, Enum):
    BRAND_UPLOAD = "brand_upload"
    CREATOR_SUPPLIED = "creator_supplied"
    PLATFORM_EXPORT = "platform_export"
    THIRD_PARTY_REPORT = "third_party_report"
    INTERNAL_REVIEW = "internal_review"


class EvidenceVerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class SupportedMetric(str, Enum):
    AGREED_COST = "agreed_cost"
    DELIVERABLES = "deliverables"
    REACH = "observed_reach"
    VIEWS = "observed_views"
    IMPRESSIONS = "observed_impressions"
    LIKES = "observed_likes"
    COMMENTS = "observed_comments"
    SHARES = "observed_shares"
    CLICKS = "observed_clicks"
    CONVERSIONS = "observed_conversions"
    REVENUE = "revenue"


class EvidenceMetadataInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    evidence_type: EvidenceType
    source_type: EvidenceSourceType
    supported_metrics: list[SupportedMetric] = Field(default_factory=list, max_length=11)
    measurement_period_start: datetime | None = None
    measurement_period_end: datetime | None = None
    captured_at: datetime | None = None
    internal_notes: list[InternalNote] = Field(default_factory=list, max_length=10)

    _start_utc = field_validator("measurement_period_start")(_aware_utc)
    _end_utc = field_validator("measurement_period_end")(_aware_utc)
    _captured_utc = field_validator("captured_at")(_aware_utc)

    @model_validator(mode="after")
    def valid_period(self):
        if self.measurement_period_start and self.measurement_period_end:
            if self.measurement_period_start > self.measurement_period_end:
                raise ValueError("measurement evidence period is invalid")
        return self


class CampaignEvidenceRecord(BaseModel):
    id: str
    campaign_performance_record_id: str
    campaign_id: str | None = None
    platform: str
    platform_id: str
    evidence_type: EvidenceType
    source_type: EvidenceSourceType
    display_filename: str
    mime_type: str
    size_bytes: int = Field(ge=1)
    checksum_present: Literal[True] = True
    evidence_status: EvidenceStatus
    verification_status: EvidenceVerificationStatus
    supported_metrics: list[SupportedMetric]
    measurement_period_start: datetime | None = None
    measurement_period_end: datetime | None = None
    captured_at: datetime | None = None
    submitted_at: datetime
    verified_at: datetime | None = None
    review_message: str | None = Field(default=None, max_length=500)
    retention_expires_at: datetime | None = None
    retention_status: Literal["active", "expired", "deleted", "indefinite"]
    consistency_status: Literal["consistent", "object_missing", "checksum_mismatch", "quarantine_failed", "storage_error"] = "consistent"
    download_available: bool
    warnings: list[str] = Field(default_factory=list)


class EvidenceReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str | None = Field(default=None, min_length=3, max_length=500)


class EvidenceRejectAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class EvidenceSupersedeAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    replacement_evidence_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=500)


class SoftDeleteAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class PerformanceCorrectionChanges(BaseModel):
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
    estimated_spend: Money | None = None
    estimated_reach: int | None = Field(default=None, ge=0)
    estimated_engagements: int | None = Field(default=None, ge=0)
    estimated_cpe: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    estimated_cpm: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    creator_quality_score_at_selection: float | None = Field(default=None, ge=0, le=100)

    _start_utc = field_validator("measurement_period_start")(_aware_utc)
    _end_utc = field_validator("measurement_period_end")(_aware_utc)

    @model_validator(mode="after")
    def has_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one correction field is required")
        return self


class CorrectionProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    base_version: int = Field(ge=1)
    proposed_changes: PerformanceCorrectionChanges
    reason: str = Field(min_length=3, max_length=1000)
    internal_notes: list[InternalNote] = Field(default_factory=list, max_length=10)


class CorrectionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class CorrectionProposal(BaseModel):
    id: str
    record_type: Literal["campaign_performance"]
    record_id: str
    base_version: int
    proposed_changes: PerformanceCorrectionChanges
    proposed_fields: list[str]
    reason: str
    status: CorrectionStatus
    submitted_at: datetime
    reviewed_at: datetime | None = None
    review_message: str | None = Field(default=None, max_length=500)
    approved_version_id: str | None = None
    retention_expires_at: datetime | None = None


class CorrectionReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class ExportCategory(str, Enum):
    PROFILES = "profiles"
    RATES = "rates"
    NEGOTIATIONS = "negotiations"
    PERFORMANCE = "performance"
    EVIDENCE = "evidence"
    CORRECTIONS = "corrections"
    AUDIT = "audit"


class TenantExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_from: datetime
    date_to: datetime
    record_categories: list[ExportCategory] = Field(min_length=1, max_length=7)
    format: Literal["json"] = "json"
    include_private_notes: bool = False
    include_deleted: bool = False
    row_limit: int = Field(default=500, ge=1, le=1000)

    _from_utc = field_validator("date_from")(_aware_utc)
    _to_utc = field_validator("date_to")(_aware_utc)

    @model_validator(mode="after")
    def bounded_range(self):
        if self.date_from > self.date_to:
            raise ValueError("date_from must not exceed date_to")
        if (self.date_to - self.date_from).days > 366:
            raise ValueError("export date range must not exceed 366 days")
        if len(self.record_categories) != len(set(self.record_categories)):
            raise ValueError("record_categories must be unique")
        return self


class TenantExportArtifact(BaseModel):
    id: str
    schema_version: Literal["1.0"] = "1.0"
    format: Literal["json"] = "json"
    record_categories: list[ExportCategory]
    row_counts: dict[str, int]
    total_rows: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    redacted_private_notes: bool
    include_deleted: bool
    created_at: datetime
    expires_at: datetime
    status: Literal["ready", "expired", "deleted"]
    download_available: bool


class AuditReviewEvent(BaseModel):
    id: str
    action: str
    record_type: str
    record_id: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    actor_category: Literal["brand", "admin", "system", "unknown"]
    created_at: datetime


class RetentionEvaluationResult(BaseModel):
    evaluated_at: datetime
    evidence_marked_expired: int = Field(ge=0)
    exports_marked_expired: int = Field(ge=0)
    already_expired: int = Field(ge=0)
    hard_deleted: Literal[0] = 0
