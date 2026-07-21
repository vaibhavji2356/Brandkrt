"""Protected FastAPI boundary for Brand Discovery preview."""

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

import security

from .config import AISettings
from .errors import AIServiceError
from .providers import build_provider
from .schemas import BrandDiscoveryPreviewResponse, BrandDiscoveryRequest
from .service import BrandDiscoveryService
from .usage import UsageIdentity


def get_brand_discovery_service() -> BrandDiscoveryService:
    try:
        settings = AISettings.from_env()
        return BrandDiscoveryService(settings, build_provider(settings))
    except AIServiceError as exc:
        raise _http_error(exc) from None


def create_router(get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/ai/brand-discovery", tags=["brand-discovery-ai"])

    @router.post("/preview", response_model=BrandDiscoveryPreviewResponse)
    async def preview_brand_discovery(
        payload: BrandDiscoveryRequest,
        request: Request,
        user: dict = Depends(get_current_user),
        _rate_limit: None = Depends(
            security.limiter_dependency("ai_brand_discovery_preview", limit=10, window=60)
        ),
        service: BrandDiscoveryService = Depends(get_brand_discovery_service),
    ):
        if user.get("role") not in {"brand", "admin"}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            return await service.preview(
                payload,
                usage_identity=UsageIdentity(
                    user_id=str(user.get("_id", "unknown")),
                    ip_address=security.client_ip(request),
                ),
            )
        except AIServiceError as exc:
            raise _http_error(exc) from None

    return router


def _http_error(exc: AIServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.public_message},
    )
