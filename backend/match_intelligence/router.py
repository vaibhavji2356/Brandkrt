"""Protected creator match endpoint with provider-failure degradation."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

import security
from brand_discovery_ai.config import AISettings
from brand_discovery_ai.usage import UsageIdentity
from research_agent.models import ResearchPackage

from .engine import MatchEngine
from .models import MatchIntelligenceResponse
from .provider import OpenAIMatchReasoningProvider


def get_match_engine() -> MatchEngine:
    try:
        settings = AISettings.from_env()
        provider = OpenAIMatchReasoningProvider(settings) if settings.openai_enabled else None
        return MatchEngine(provider)
    except Exception:
        return MatchEngine()


def create_match_router(get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/ai/match", tags=["match-intelligence"])

    @router.post("/recommendations", response_model=MatchIntelligenceResponse)
    async def recommendations(
        package: ResearchPackage,
        request: Request,
        user: dict = Depends(get_current_user),
        _rate_limit: None = Depends(security.limiter_dependency("ai_match_recommendations", limit=10, window=60)),
        engine: MatchEngine = Depends(get_match_engine),
    ):
        if user.get("role") not in {"brand", "admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return await engine.recommend(
            package,
            usage_identity=UsageIdentity(
                user_id=str(user.get("_id", "unknown")),
                ip_address=security.client_ip(request),
            ),
        )

    return router
