"""Protected, additive creator-intelligence endpoint."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

import security
from brand_discovery_ai.config import AISettings
from brand_discovery_ai.usage import UsageIdentity
from commercial_intelligence.service import CommercialService

from .engine import CreatorIntelligenceEngine
from .models import CreatorIntelligenceRequest, CreatorIntelligenceResponse
from .narrative import CreatorNarrativeService
from .narrative_provider import OpenAICreatorNarrativeProvider


def get_creator_intelligence_engine() -> CreatorIntelligenceEngine:
    return CreatorIntelligenceEngine()


def get_creator_narrative_service() -> CreatorNarrativeService:
    try:
        settings = AISettings.from_env()
        provider = OpenAICreatorNarrativeProvider(settings) if settings.openai_enabled else None
        return CreatorNarrativeService(provider)
    except Exception:
        return CreatorNarrativeService()


def create_creator_intelligence_router(get_current_user: Callable,
                                       database_provider: Callable | None = None) -> APIRouter:
    router = APIRouter(prefix="/ai/creator-intelligence", tags=["creator-intelligence"])

    @router.post("/recommendations", response_model=CreatorIntelligenceResponse)
    async def recommendations(
        payload: CreatorIntelligenceRequest,
        request: Request,
        user: dict = Depends(get_current_user),
        _rate_limit: None = Depends(security.limiter_dependency("creator_intelligence_recommendations", limit=10, window=60)),
        engine: CreatorIntelligenceEngine = Depends(get_creator_intelligence_engine),
        narrative: CreatorNarrativeService = Depends(get_creator_narrative_service),
    ):
        if user.get("role") not in {"brand", "admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
        history_warnings: list[str] = []
        effective_payload = payload
        if payload.use_commercial_history:
            if database_provider is None:
                raise HTTPException(status_code=503, detail="Commercial history is unavailable")
            effective_payload, history_warnings = await CommercialService(database_provider()).apply_history(user, payload)
        result = engine.recommend(effective_payload)
        if history_warnings:
            result = result.model_copy(update={
                "warnings": list(dict.fromkeys([*result.warnings, *history_warnings])),
            })
        return await narrative.enrich(
            effective_payload, result,
            UsageIdentity(user_id=str(user.get("_id", "unknown")), ip_address=security.client_ip(request)),
        )

    return router
