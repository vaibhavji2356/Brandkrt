"""Runtime health and startup timing for BrandKrt.

This module deliberately has no FastAPI or domain imports so future backend
modules can reuse the same status service without creating import cycles.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional


logger = logging.getLogger("brandkrt.status")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackendStatus:
    """Tracks process health, dependency readiness, and startup timings."""

    def __init__(self) -> None:
        self._boot_monotonic = time.perf_counter()
        self._booted_at = _utc_iso()
        self._app_started_at: Optional[str] = None
        self._app_boot_ms: Optional[float] = None
        self._database_connected = False
        self._mongo_connection_ms: Optional[float] = None
        self._last_mongo_ping_ms: Optional[float] = None
        self._readiness_ms: Optional[float] = None
        self._ready = False

    @property
    def environment(self) -> str:
        return os.environ.get("APP_ENV", "development").strip().lower() or "development"

    @property
    def version(self) -> str:
        return os.environ.get("APP_VERSION", "1.0.0").strip() or "1.0.0"

    def mark_app_started(self) -> None:
        if self._app_started_at is not None:
            return
        self._app_started_at = _utc_iso()
        self._app_boot_ms = round((time.perf_counter() - self._boot_monotonic) * 1000, 2)
        logger.info("[STARTUP] app_boot_ms=%.2f", self._app_boot_ms)

    def configuration_status(self) -> Dict[str, Any]:
        required = {
            "MONGO_URL": bool(os.environ.get("MONGO_URL", "").strip()),
            "DB_NAME": bool(os.environ.get("DB_NAME", "").strip()),
            "JWT_SECRET": bool(os.environ.get("JWT_SECRET", "").strip()),
        }
        environment = self.environment
        if environment in {"production", "prod", "staging"}:
            secret = os.environ.get("JWT_SECRET", "")
            required["JWT_SECRET_STRONG"] = len(secret) >= 32

        services: Dict[str, Dict[str, Any]] = {}

        google_configured = bool(
            os.environ.get("GOOGLE_CLIENT_ID")
            or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            or os.environ.get("REACT_APP_GOOGLE_CLIENT_ID")
        )
        google_dependency = True
        if google_configured:
            try:
                import google.auth  # noqa: F401
            except Exception:
                google_dependency = False
        services["googleAuth"] = {
            "required": google_configured,
            "configured": google_configured,
            "available": google_dependency if google_configured else True,
        }

        email_provider = os.environ.get("EMAIL_PROVIDER", "auto").strip().lower() or "auto"
        production_like = environment in {"production", "prod", "staging"}
        smtp_configured = all(os.environ.get(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
        if email_provider == "resend":
            email_configured = bool(os.environ.get("RESEND_API_KEY"))
            try:
                import resend  # noqa: F401
            except Exception:
                email_configured = False
        elif email_provider == "smtp" or production_like:
            email_configured = smtp_configured
        else:
            email_configured = True
        services["email"] = {
            "required": production_like or email_provider in {"smtp", "resend"},
            "provider": email_provider,
            "configured": email_configured,
            "available": email_configured,
        }

        payment_provider = os.environ.get("PAYMENT_PROVIDER", "stub").strip().strip("'\"").lower() or "stub"
        payment_configured = True
        if payment_provider == "stripe":
            payment_configured = bool(os.environ.get("STRIPE_SECRET_KEY"))
        elif payment_provider == "razorpay":
            payment_configured = all(os.environ.get(key) for key in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"))
        services["payments"] = {
            "required": payment_provider not in {"", "stub"},
            "provider": payment_provider,
            "configured": payment_configured,
            "available": payment_configured,
        }

        config_ready = all(required.values())
        services_ready = all(not item["required"] or item["available"] for item in services.values())
        return {
            "valid": config_ready and services_ready,
            "required": required,
            "services": services,
        }

    async def check_readiness(
        self,
        mongo_ping: Callable[[], Awaitable[Any]],
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        config = self.configuration_status()
        database_error: Optional[str] = None
        mongo_started = time.perf_counter()
        try:
            await mongo_ping()
            self._database_connected = True
        except Exception as exc:
            self._database_connected = False
            database_error = type(exc).__name__
        mongo_ping_ms = round((time.perf_counter() - mongo_started) * 1000, 2)
        self._last_mongo_ping_ms = mongo_ping_ms
        if self._database_connected and self._mongo_connection_ms is None:
            self._mongo_connection_ms = mongo_ping_ms
        ready_now = bool(self._database_connected and config["valid"])
        check_ms = round((time.perf_counter() - started) * 1000, 2)
        if ready_now and self._readiness_ms is None:
            # Capture the first dependency-ready duration once. Repeated health
            # probes must not rewrite startup metrics with warm-pool timings.
            app_boot_ms = self._app_boot_ms or 0.0
            self._readiness_ms = round(app_boot_ms + check_ms, 2)
        self._ready = ready_now

        logger.info(
            "[READINESS] ready=%s mongo_connected=%s mongo_ping_ms=%.2f "
            "readiness_ms=%s check_ms=%.2f",
            self._ready,
            self._database_connected,
            mongo_ping_ms,
            self._readiness_ms,
            check_ms,
        )
        return self.snapshot(configuration=config, database_error=database_error, check_ms=check_ms)

    def snapshot(
        self,
        *,
        configuration: Optional[Dict[str, Any]] = None,
        database_error: Optional[str] = None,
        check_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "isReady": self._ready,
            "isDatabaseConnected": self._database_connected,
            "uptime": round(time.perf_counter() - self._boot_monotonic, 3),
            "startupTime": self._booted_at,
            "version": self.version,
            "environment": self.environment,
            "timings": {
                "appBootMs": self._app_boot_ms,
                "mongoConnectionMs": self._mongo_connection_ms,
                "lastMongoPingMs": self._last_mongo_ping_ms,
                "readinessMs": self._readiness_ms,
            },
        }
        if configuration is not None:
            result["configuration"] = configuration
        if database_error:
            result["databaseError"] = database_error
        if check_ms is not None:
            result["timings"]["lastReadinessCheckMs"] = check_ms
        return result


backend_status = BackendStatus()
