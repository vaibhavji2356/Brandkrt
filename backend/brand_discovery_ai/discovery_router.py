"""Authenticated, role-protected mock multi-platform discovery preview."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

import security
from .discovery_schemas import DiscoveryCriteria, DiscoveryPreviewResponse
from .discovery_service import MultiPlatformDiscoveryService


def get_multi_platform_discovery_service() -> MultiPlatformDiscoveryService:
    return MultiPlatformDiscoveryService()


def create_discovery_router(get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/ai/discovery", tags=["multi-platform-discovery"])

    @router.post("/preview", response_model=DiscoveryPreviewResponse)
    async def preview(
        payload: DiscoveryCriteria,
        user: dict = Depends(get_current_user),
        _rate_limit: None = Depends(security.limiter_dependency("ai_discovery_preview", limit=10, window=60)),
        service: MultiPlatformDiscoveryService = Depends(get_multi_platform_discovery_service),
    ):
        if user.get("role") not in {"brand", "admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return await service.preview(payload)

    return router
