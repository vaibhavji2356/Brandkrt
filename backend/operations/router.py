"""Admin-only low-cardinality metrics and operational diagnostics."""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Response

from backend_status import backend_status
from brand_discovery_ai.metrics import ai_metrics
from brand_discovery_ai.usage import ai_usage_accounting
from commercial_intelligence.hardening_repository import HardeningRepository
from operations.metrics import operational_metrics
from operations.rate_limiting import rate_limiter


def create_operations_router(get_current_user: Callable, database_provider: Callable, storage_provider: Callable):
    router = APIRouter(prefix="/admin/operations", tags=["operations"])

    def admin(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        return user

    @router.get("/diagnostics")
    async def diagnostics(_user: dict = Depends(admin)):
        storage = storage_provider()
        snapshot = backend_status.snapshot()
        inconsistencies = await HardeningRepository(database_provider()).inconsistency_counts()
        return {
            "service": "brandkrt-api", "version": snapshot["version"], "commit": snapshot["commit"],
            "environment": snapshot["environment"], "uptime_seconds": snapshot["uptime"],
            "ready": snapshot["isReady"], "database_ready": snapshot["isDatabaseConnected"],
            "components": snapshot.get("components", {}),
            "storage": {"provider": storage.provider_name, "durable": storage.durable},
            "rate_limit_backend": rate_limiter.backend_name,
            "ai_usage_backend": ai_usage_accounting.snapshot().get("backend", "unknown"),
            "evidence_consistency_counts": inconsistencies,
            "failure_counts": operational_metrics.snapshot()["counters"],
            "ai_provider_aggregates": ai_metrics.snapshot(),
        }

    @router.get("/metrics", response_class=Response)
    async def metrics(_user: dict = Depends(admin)):
        body = operational_metrics.prometheus() + _ai_prometheus(ai_metrics.snapshot())
        return Response(
            body, media_type="text/plain; version=0.0.4; charset=utf-8",
            headers={"Cache-Control": "private, no-store"},
        )

    return router


def _ai_prometheus(snapshot: dict) -> str:
    lines = []
    allowed = {
        "requests", "successes", "failures", "timeouts", "retries", "budget_rejections",
        "estimated_input_tokens", "estimated_output_tokens", "actual_input_tokens",
        "actual_output_tokens", "estimated_cost_usd", "actual_cost_usd",
    }
    for provider, values in sorted(snapshot.items()):
        safe_provider = "".join(char for char in provider if char.isalnum() or char in "_-")[:40] or "unknown"
        for name in sorted(allowed):
            value = values.get(name)
            if isinstance(value, (int, float)):
                metric = "".join(char for char in name if char.isalnum() or char == "_")
                lines.append(f'brandkrt_ai_{metric}{{provider="{safe_provider}"}} {value}')
    return "\n".join(lines) + ("\n" if lines else "")
