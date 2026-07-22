"""Tenant-scoped commercial history, performance, and analytics routes."""

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import APIRouter, Depends, Query

import security

from .models import (
    AnalyticsSummary, CampaignPerformanceCreate, CampaignPerformancePatch,
    CampaignPerformanceRecord, CommercialProfile, CommercialProfileCreate,
    CommercialProfilePatch, NegotiationCreate, NegotiationRecord,
    PerformanceComparison, RateHistoryCreate, RateHistoryRecord,
)
from .service import CommercialService


def create_commercial_intelligence_routers(get_current_user: Callable, database_provider: Callable):
    commercial = APIRouter(prefix="/creator-commercial", tags=["creator-commercial"])
    performance = APIRouter(prefix="/campaign-performance", tags=["campaign-performance"])

    def service() -> CommercialService:
        return CommercialService(database_provider())

    read_limit = security.limiter_dependency("commercial_intelligence_read", limit=120, window=60)
    write_limit = security.limiter_dependency("commercial_intelligence_write", limit=30, window=60)

    @commercial.get("/analytics/summary", response_model=AnalyticsSummary)
    async def analytics_summary(
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        end_value = end or datetime.now(timezone.utc)
        start_value = start or end_value - timedelta(days=90)
        return await manager.analytics(user, start_value, end_value, limit, currency)

    @commercial.post("/profiles", response_model=CommercialProfile, status_code=201)
    async def create_profile(
        payload: CommercialProfileCreate,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.create_profile(user, payload)

    @commercial.get("/profiles", response_model=list[CommercialProfile])
    async def list_profiles(
        limit: int = Query(default=50, ge=1, le=100),
        platform: str | None = Query(default=None, pattern=r"^(instagram|youtube|snapchat|twitch|x)$"),
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.list_profiles(user, limit, platform)

    @commercial.get("/profiles/{profile_id}", response_model=CommercialProfile)
    async def get_profile(
        profile_id: str,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.get_profile(user, profile_id)

    @commercial.patch("/profiles/{profile_id}", response_model=CommercialProfile)
    async def patch_profile(
        profile_id: str, payload: CommercialProfilePatch,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.patch_profile(user, profile_id, payload)

    @commercial.post("/profiles/{profile_id}/rates", response_model=RateHistoryRecord, status_code=201)
    async def append_rate(
        profile_id: str, payload: RateHistoryCreate,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.append_rate(user, profile_id, payload)

    @commercial.get("/profiles/{profile_id}/rates", response_model=list[RateHistoryRecord])
    async def list_rates(
        profile_id: str, limit: int = Query(default=50, ge=1, le=100),
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.list_rates(user, profile_id, limit)

    @commercial.post("/profiles/{profile_id}/negotiations", response_model=NegotiationRecord, status_code=201)
    async def append_negotiation(
        profile_id: str, payload: NegotiationCreate,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.append_negotiation(user, profile_id, payload)

    @commercial.get("/profiles/{profile_id}/negotiations", response_model=list[NegotiationRecord])
    async def list_negotiations(
        profile_id: str, limit: int = Query(default=50, ge=1, le=100),
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.list_negotiations(user, profile_id, limit)

    @performance.post("", response_model=CampaignPerformanceRecord, status_code=201)
    async def create_performance(
        payload: CampaignPerformanceCreate,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.create_performance(user, payload)

    @performance.get("", response_model=list[CampaignPerformanceRecord])
    async def list_performance(
        limit: int = Query(default=50, ge=1, le=100),
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.list_performance(user, limit)

    @performance.get("/{record_id}/comparison", response_model=PerformanceComparison)
    async def performance_comparison(
        record_id: str,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.comparison(user, record_id)

    @performance.get("/{record_id}", response_model=CampaignPerformanceRecord)
    async def get_performance(
        record_id: str,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(read_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.get_performance(user, record_id)

    @performance.patch("/{record_id}", response_model=CampaignPerformanceRecord)
    async def patch_performance(
        record_id: str, payload: CampaignPerformancePatch,
        user: dict = Depends(get_current_user),
        _limit: None = Depends(write_limit),
        manager: CommercialService = Depends(service),
    ):
        return await manager.patch_performance(user, record_id, payload)

    return commercial, performance
