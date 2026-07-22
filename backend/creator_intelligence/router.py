"""Protected, additive creator-intelligence endpoint."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

import security

from .engine import CreatorIntelligenceEngine
from .models import CreatorIntelligenceRequest, CreatorIntelligenceResponse


def get_creator_intelligence_engine() -> CreatorIntelligenceEngine:
    return CreatorIntelligenceEngine()


def create_creator_intelligence_router(get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/ai/creator-intelligence", tags=["creator-intelligence"])

    @router.post("/recommendations", response_model=CreatorIntelligenceResponse)
    async def recommendations(
        payload: CreatorIntelligenceRequest,
        user: dict = Depends(get_current_user),
        _rate_limit: None = Depends(security.limiter_dependency("creator_intelligence_recommendations", limit=10, window=60)),
        engine: CreatorIntelligenceEngine = Depends(get_creator_intelligence_engine),
    ):
        if user.get("role") not in {"brand", "admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return engine.recommend(payload)

    return router
