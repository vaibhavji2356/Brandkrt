"""Research task and package contracts, separate from discovery API schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from brand_discovery_ai.discovery_schemas import NormalizedProfile
from brand_discovery_ai.identity import IdentitySuggestion


class TaskType(str, Enum):
    CREATOR_SEARCH = "creator_search"
    BRAND_SEARCH = "brand_search"
    PROFILE_LOOKUP = "profile_lookup"
    KEYWORD_LOOKUP = "keyword_lookup"
    WEBSITE_LOOKUP = "website_lookup"
    PLATFORM_LOOKUP = "platform_lookup"
    FUTURE_CUSTOM_TASK = "future_custom_task"


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class ResearchTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=100)
    type: TaskType
    priority: TaskPriority = TaskPriority.NORMAL
    platform: str | None = Field(default=None, max_length=40)
    entity_type: Literal["creator", "brand"] | None = None
    query: str = Field(min_length=1, max_length=500)
    status: TaskStatus = TaskStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    entities: list[NormalizedProfile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RankingSummaryItem(BaseModel):
    entity_key: str
    score: float
    components: dict[str, float | None]
    warnings: list[str] = Field(default_factory=list)


class SourceSummaryItem(BaseModel):
    source: str
    entity_count: int = Field(ge=0)
    average_confidence: float = Field(ge=0, le=1)


class ContextSizeEstimate(BaseModel):
    characters: int = Field(ge=0)
    estimated_tokens: int = Field(ge=0)
    included_entities: int = Field(ge=0)
    omitted_entities: int = Field(ge=0)
    token_limit: int = Field(gt=0)


class BuiltContext(BaseModel):
    """AI-ready facts only. Task IDs, statuses, priorities and metadata are excluded."""

    request: dict[str, Any]
    entities: list[dict[str, Any]]
    ranking: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class ResearchPackage(BaseModel):
    request_summary: dict[str, Any]
    normalized_entities: list[NormalizedProfile]
    ranking_summary: list[RankingSummaryItem]
    identity_suggestions: list[IdentitySuggestion]
    warnings: list[str]
    missing_information: list[str]
    confidence: float = Field(ge=0, le=1)
    source_summary: list[SourceSummaryItem]
    context_size_estimate: ContextSizeEstimate
    ai_context: BuiltContext


class ResearchRun(BaseModel):
    tasks: list[ResearchTask]
    results: list[TaskResult]
    package: ResearchPackage
