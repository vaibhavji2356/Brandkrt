"""Admin-only HTTP API for research jobs, lead workflow, analytics, and AI activity."""

from __future__ import annotations

from functools import lru_cache
import os
from typing import Callable, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

import security
from brand_discovery_ai.discovery_schemas import EntityType, Platform
from brand_discovery_ai.source_adapters import build_source_adapters
from brand_discovery_ai.usage import UsageIdentity
from match_intelligence.router import get_match_engine
from research_agent.agent import ResearchAgent
from research_agent.dispatcher import ResearchDispatcher
from research_agent.provider_orchestrator import ProviderOrchestrator

from .models import (
    AIActivityPage, AdminResearchRequest, AuditEvent, LeadAnalytics, LeadNoteRequest,
    LeadPriority, LeadStatus, LeadUpdateRequest, ResearchHistoryPage,
    ResearchJobDetail, ResearchJobStatus, ResearchJobSummary, SaveLeadRequest,
    SavedLead, SavedLeadPage,
)
from .repository import AdminLeadRepository
from .service import AdminLeadService


@lru_cache(maxsize=1)
def get_admin_research_agent() -> ResearchAgent:
    environment = os.environ.get("APP_ENV", "development").strip().casefold()
    mock_mode = os.environ.get("ADMIN_LEAD_MOCK_MODE", "false").strip().casefold() in {
        "1", "true", "yes", "on",
    }
    if environment not in {"production", "prod", "staging"} and mock_mode:
        return ResearchAgent()
    adapters = build_source_adapters()
    # Instagram and Snapchat remain intentionally unavailable until official
    # factual providers are implemented; synthetic adapters never enter production research.
    factual = [adapters[platform] for platform in (Platform.YOUTUBE, Platform.TWITCH, Platform.X)]
    dispatcher = ResearchDispatcher(
        orchestrator=ProviderOrchestrator(factual, concurrent=True),
    )
    return ResearchAgent(dispatcher=dispatcher)


def create_admin_lead_router(get_current_user: Callable, database_provider: Callable) -> APIRouter:
    router = APIRouter(prefix="/admin/lead-intelligence", tags=["admin-lead-intelligence"])

    def admin(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return user

    def service() -> AdminLeadService:
        return AdminLeadService(
            AdminLeadRepository(database_provider()), get_admin_research_agent(), get_match_engine(),
        )

    read_limit = security.limiter_dependency("admin_lead_read", limit=180, window=60)
    write_limit = security.limiter_dependency("admin_lead_write", limit=40, window=60)
    research_limit = security.limiter_dependency("admin_lead_research", limit=10, window=60)

    @router.post(
        "/research/jobs", response_model=ResearchJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_research_job(
        payload: AdminResearchRequest, background: BackgroundTasks, request: Request,
        user: dict = Depends(admin), _limit: None = Depends(research_limit),
        manager: AdminLeadService = Depends(service),
    ):
        job = await manager.create_job(payload, user)
        background.add_task(
            manager.run_job, job.id, payload, user,
            UsageIdentity(user_id=str(user.get("_id", "unknown")), ip_address=security.client_ip(request)),
        )
        return job

    @router.get("/research/jobs/{job_id}", response_model=ResearchJobDetail)
    async def get_research_job(
        job_id: str, _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.get_job(job_id)

    @router.get("/research/history", response_model=ResearchHistoryPage)
    async def research_history(
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=20, ge=1, le=50),
        search: str | None = Query(default=None, max_length=100),
        entity_type: Literal["creator", "brand", "both"] | None = None,
        platform: Platform | None = None,
        job_status: ResearchJobStatus | None = Query(default=None, alias="status"),
        sort_by: Literal["created_at", "results", "confidence"] = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.history(
            page=page, page_size=page_size, search=search, entity_type=entity_type,
            platform=platform.value if platform else None,
            status=job_status.value if job_status else None,
            sort_by=sort_by, sort_order=sort_order,
        )

    @router.post(
        "/research/history/{job_id}/rerun", response_model=ResearchJobSummary,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def rerun_research(
        job_id: str, background: BackgroundTasks, request: Request,
        user: dict = Depends(admin), _limit: None = Depends(research_limit),
        manager: AdminLeadService = Depends(service),
    ):
        job, payload = await manager.rerun(job_id, user)
        background.add_task(
            manager.run_job, job.id, payload, user,
            UsageIdentity(user_id=str(user.get("_id", "unknown")), ip_address=security.client_ip(request)),
        )
        return job

    @router.post("/leads", response_model=SavedLead)
    async def save_lead(
        payload: SaveLeadRequest, user: dict = Depends(admin),
        _limit: None = Depends(write_limit), manager: AdminLeadService = Depends(service),
    ):
        return await manager.save_lead(payload, user)

    @router.get("/leads", response_model=SavedLeadPage)
    async def list_leads(
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=20, ge=1, le=50),
        search: str | None = Query(default=None, max_length=100),
        entity_type: Literal["creator", "brand"] | None = None,
        platform: Platform | None = None,
        lead_status: LeadStatus | None = Query(default=None, alias="status"),
        priority: LeadPriority | None = None,
        archived: bool = False,
        sort_by: Literal["updated_at", "created_at", "priority", "recommendation"] = "updated_at",
        sort_order: Literal["asc", "desc"] = "desc",
        _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.leads(
            page=page, page_size=page_size, search=search, entity_type=entity_type,
            platform=platform.value if platform else None,
            status=lead_status.value if lead_status else None,
            priority=priority.value if priority else None, archived=archived,
            sort_by=sort_by, sort_order=sort_order,
        )

    @router.get("/leads/{lead_id}", response_model=SavedLead)
    async def get_lead(
        lead_id: str, _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.get_lead(lead_id)

    @router.patch("/leads/{lead_id}", response_model=SavedLead)
    async def update_lead(
        lead_id: str, payload: LeadUpdateRequest, user: dict = Depends(admin),
        _limit: None = Depends(write_limit), manager: AdminLeadService = Depends(service),
    ):
        return await manager.update_lead(lead_id, payload, user)

    @router.post("/leads/{lead_id}/notes", response_model=SavedLead)
    async def add_note(
        lead_id: str, payload: LeadNoteRequest, user: dict = Depends(admin),
        _limit: None = Depends(write_limit), manager: AdminLeadService = Depends(service),
    ):
        return await manager.add_note(lead_id, payload, user)

    @router.post("/leads/{lead_id}/archive", response_model=SavedLead)
    async def archive_lead(
        lead_id: str, user: dict = Depends(admin),
        _limit: None = Depends(write_limit), manager: AdminLeadService = Depends(service),
    ):
        return await manager.archive(lead_id, user)

    @router.get("/leads/{lead_id}/audit", response_model=list[AuditEvent])
    async def lead_audit(
        lead_id: str, limit: int = Query(default=50, ge=1, le=100),
        _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.audit(lead_id, limit)

    @router.get("/analytics", response_model=LeadAnalytics)
    @router.get("/dashboard", response_model=LeadAnalytics, include_in_schema=False)
    async def analytics(
        _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.analytics()

    @router.get("/activity", response_model=AIActivityPage)
    async def ai_activity(
        page: int = Query(default=1, ge=1, le=10_000),
        page_size: int = Query(default=20, ge=1, le=50),
        _user: dict = Depends(admin), _limit: None = Depends(read_limit),
        manager: AdminLeadService = Depends(service),
    ):
        return await manager.ai_activity(page, page_size)

    return router
