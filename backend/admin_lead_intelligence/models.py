"""Strict public contracts for the admin Lead Intelligence workspace."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, EntityType, Platform


class ResearchJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LeadPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACT_PLANNED = "contact_planned"
    CONTACTED = "contacted"
    FOLLOW_UP_REQUIRED = "follow_up_required"
    REPLIED = "replied"
    NEGOTIATING = "negotiating"
    CONVERTED = "converted"
    CLOSED = "closed"


class AdminResearchRequest(DiscoveryCriteria):
    """Discovery criteria plus admin-workspace presentation preferences."""

    research_name: str | None = Field(default=None, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    minimum_audience_quality: float | None = Field(default=None, ge=0, le=100)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")

    def discovery_criteria(self) -> DiscoveryCriteria:
        values = self.model_dump(exclude={
            "research_name", "industry", "minimum_audience_quality", "currency",
        })
        if self.industry and not values.get("niche"):
            values["niche"] = self.industry
        return DiscoveryCriteria.model_validate(values)


class PriorityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0, le=100)
    priority: LeadPriority
    components: dict[str, float | None]
    explanation: list[str] = Field(max_length=10)


class GroundedAssistance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    why_contact: str = Field(max_length=600)
    campaign_fit: str = Field(max_length=600)
    outreach_angle: str = Field(max_length=600)
    conversation_starter: str = Field(max_length=600)
    negotiation_guidance: str = Field(max_length=600)
    reasoning_source: str = Field(max_length=80)
    degraded: bool


class PricingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estimated_rate: float | None = Field(default=None, ge=0)
    selected_rate: float | None = Field(default=None, ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    rate_type: str | None = Field(default=None, max_length=50)
    confidence: float = Field(ge=0, le=1)
    source: str | None = Field(default=None, max_length=120)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class CommercialSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    available: bool
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    known_rate: float | None = Field(default=None, ge=0)
    negotiated_rate: float | None = Field(default=None, ge=0)
    verification_status: str | None = Field(default=None, max_length=40)


class LeadIntelligenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_key: str = Field(min_length=3, max_length=420)
    entity_type: Literal["creator", "brand"]
    platform: Platform
    platform_id: str = Field(min_length=1, max_length=200)
    username: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    profile_url: str | None = None
    biography: str | None = Field(default=None, max_length=2000)
    website: str | None = None
    public_social_profiles: list[str] = Field(default_factory=list, max_length=20)
    available_platforms: list[str] = Field(default_factory=list, max_length=10)
    categories: list[str] = Field(default_factory=list, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    language: str | None = Field(default=None, max_length=35)
    follower_count: int | None = Field(default=None, ge=0)
    content_count: int | None = Field(default=None, ge=0)
    average_views: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0, le=100)
    audience_quality: float | None = Field(default=None, ge=0, le=100)
    marketing_signals: list[str] = Field(default_factory=list, max_length=12)
    estimated_collaboration_activity: str | None = Field(default=None, max_length=300)
    verification_status: Literal["verified", "not_verified", "unavailable"]
    last_observed_activity: datetime | None = None
    collected_at: datetime
    discovery_source: str = Field(max_length=100)
    confidence: float = Field(ge=0, le=100)
    recommendation_score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    weaknesses: list[str] = Field(default_factory=list, max_length=8)
    why_recommended: list[str] = Field(default_factory=list, max_length=8)
    priority: PriorityScore
    assistance: GroundedAssistance
    pricing: PricingSummary | None = None
    commercial_history: CommercialSummary
    possible_duplicates: list[str] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=30)


class ResearchJobSummary(BaseModel):
    id: str
    research_name: str | None = None
    entity_type: EntityType
    platforms: list[Platform]
    query_summary: str
    status: ResearchJobStatus
    progress: int = Field(ge=0, le=100)
    result_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=100)
    reasoning_source: str | None = None
    degraded: bool = False
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ResearchJobDetail(ResearchJobSummary):
    criteria: dict
    results: list[LeadIntelligenceResult]
    warnings: list[str]
    missing_information: list[str]
    source_summary: list[dict]


class ResearchHistoryPage(BaseModel):
    items: list[ResearchJobSummary]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class SaveLeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_id: str = Field(min_length=24, max_length=24, pattern=r"^[a-fA-F0-9]{24}$")
    entity_key: str = Field(min_length=3, max_length=420)


class LeadUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: LeadStatus


class LeadNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("note")
    @classmethod
    def compact_note(cls, value: str) -> str:
        return " ".join(value.split())


class LeadNote(BaseModel):
    note: str
    created_at: datetime


class SavedLead(BaseModel):
    id: str
    research_id: str
    fingerprint: str
    status: LeadStatus
    archived: bool
    result: LeadIntelligenceResult
    notes: list[LeadNote]
    created_at: datetime
    updated_at: datetime


class SavedLeadPage(BaseModel):
    items: list[SavedLead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class AuditEvent(BaseModel):
    action: str
    changed_fields: list[str]
    created_at: datetime


class LeadAnalytics(BaseModel):
    brands_found: int = Field(ge=0)
    creators_found: int = Field(ge=0)
    high_priority_leads: int = Field(ge=0)
    contacted: int = Field(ge=0)
    replies: int = Field(ge=0)
    converted: int = Field(ge=0)
    research_volume: int = Field(ge=0)
    saved_leads: int = Field(ge=0)
    top_niches: list[dict]
    top_platforms: list[dict]
    recent_activity: list[dict]


class AIActivityPage(BaseModel):
    items: list[dict]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
