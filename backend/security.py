"""Part 5 — Production security layer.

Provides:
- SecurityHeaders middleware (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, HSTS in prod)
- Origin / Referer CSRF mitigation for state-changing requests
- Generic per-IP rate limiter for sensitive endpoints (register, forgot-password, contact, oauth)
- Production-safe logging configuration helper

All additive. No existing routes are modified.
"""
from __future__ import annotations

import logging
import os
import time
import ipaddress
from collections import defaultdict, deque
from typing import Iterable, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from operations.metrics import operational_metrics
from operations.rate_limiting import RateLimitBackendUnavailable, rate_limiter

logger = logging.getLogger("brandkrt.security")

# ---------- Logging ----------
class _SecretRedactor(logging.Filter):
    KEYS = ("password", "password_hash", "token", "access_token", "refresh_token",
            "api_key", "authorization", "resend_api_key", "cloudinary", "stripe")

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            msg = str(record.getMessage())
            low = msg.lower()
            for k in self.KEYS:
                if k in low:
                    # do not actually scrub the string we already formatted –
                    # just downgrade to INFO if it slipped through DEBUG paths
                    record.msg = "[redacted - sensitive content filtered]"
                    record.args = ()
                    break
        except Exception:
            pass
        return True


def configure_logging() -> None:
    """Production-safe logging. INFO in prod, DEBUG in dev."""
    from operations.observability import configure_structured_logging

    env = os.environ.get("APP_ENV", "development").lower()
    level = logging.INFO if env != "development" else logging.DEBUG
    root = logging.getLogger()
    if not any(isinstance(f, _SecretRedactor) for f in root.filters):
        root.addFilter(_SecretRedactor())
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        force=False,
    )
    configure_structured_logging()
    for handler in logging.getLogger().handlers:
        if not any(isinstance(item, _SecretRedactor) for item in handler.filters):
            handler.addFilter(_SecretRedactor())
    # tame noisy libs in prod
    for noisy in ("uvicorn.access", "multipart.multipart", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------- Middleware: security headers ----------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds defence-in-depth security headers on every response."""

    def __init__(self, app, prod: bool = False):
        super().__init__(app)
        self.prod = prod

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy",
                           "camera=(), microphone=(), geolocation=(), interest-cohort=()")
        headers.setdefault("X-XSS-Protection", "0")
        if self.prod:
            headers.setdefault("Strict-Transport-Security",
                               "max-age=63072000; includeSubDomains; preload")
        return response


# ---------- Middleware: Origin-based CSRF mitigation ----------
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCSRFMiddleware(BaseHTTPMiddleware):
    """For state-changing requests, require Origin (or Referer) to be in an
    allow-list. This protects against classic CSRF when cookies are used.

    Idempotent reads (GET/HEAD/OPTIONS) and the auth-bootstrap routes are skipped
    so that token-based callers and same-origin SSR work uninterrupted.
    """

    def __init__(self, app, allow_origins: Iterable[str]):
        super().__init__(app)
        # normalise (strip trailing slash, lowercase scheme/host)
        self.allowed = {o.rstrip("/").lower() for o in allow_origins if o}
        # exempt paths that need to be hit cross-origin without a real Origin
        # (e.g. server-to-server health checks, the Google OAuth callback POST
        # already authorises itself via a verified ID token).
        self.exempt_prefixes = (
            "/api/health",
            "/api/auth/google",  # secured by Google ID-token verification
            "/uploads/",
        )

    async def dispatch(self, request: Request, call_next):
        if request.method in UNSAFE_METHODS and self.allowed:
            path = request.url.path
            if not any(path.startswith(p) for p in self.exempt_prefixes):
                origin = (request.headers.get("origin") or "").rstrip("/").lower()
                referer = (request.headers.get("referer") or "").lower()
                if not origin and referer:
                    # derive origin from referer for older browsers
                    try:
                        from urllib.parse import urlsplit
                        s = urlsplit(referer)
                        origin = f"{s.scheme}://{s.netloc}".lower()
                    except Exception:
                        origin = ""
                if origin and origin not in self.allowed:
                    return Response("Forbidden origin", status_code=403)
        return await call_next(request)


# ---------- Simple in-memory rate limiter ----------
# NOTE: in-memory, suitable for single-worker deployments (Render free / hobby).
# For multi-worker production use a Redis-backed limiter — interface stays the same.
class _LegacyRateLimitBuckets(defaultdict):
    """Reset both legacy and selectable in-memory backends for compatibility."""

    def clear(self) -> None:
        super().clear()
        reset = getattr(rate_limiter.backend, "reset", None)
        if callable(reset):
            reset()


_RL_BUCKETS: "defaultdict[str, deque[float]]" = _LegacyRateLimitBuckets(deque)


def rate_limit(key: str, *, limit: int = 10, window: int = 60) -> None:
    """Raise 429 if `key` exceeded `limit` calls within `window` seconds."""
    now = time.time()
    bucket = _RL_BUCKETS[key]
    while bucket and (now - bucket[0]) > window:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
    bucket.append(now)


def client_ip(request: Request) -> str:
    direct = request.client.host if request.client else "unknown"
    if os.environ.get("TRUST_PROXY_HEADERS", "false").strip().casefold() not in {"1", "true", "yes", "on"}:
        return _safe_ip(direct)
    values = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
    try:
        trusted_hops = max(1, min(int(os.environ.get("TRUSTED_PROXY_HOPS", "1")), 5))
    except ValueError:
        trusted_hops = 1
    if len(values) >= trusted_hops:
        return _safe_ip(values[-trusted_hops])
    return _safe_ip(direct)


def limiter_dependency(action: str, limit: int = 10, window: int = 60):
    """FastAPI Depends() factory. Use:  Depends(limiter_dependency('register', 5, 300))"""
    async def _dep(request: Request, response: Response) -> None:
        key = f"{action}:{client_ip(request)}"
        try:
            decision = await rate_limiter.acquire(key, limit, window)
        except RateLimitBackendUnavailable:
            operational_metrics.increment("rate_limit_backend_failures")
            raise HTTPException(
                status_code=503, detail="Request protection is temporarily unavailable.",
                headers={"Retry-After": "5"},
            ) from None
        if not decision.allowed:
            operational_metrics.increment("rate_limit_rejections")
            raise HTTPException(
                status_code=429, detail="Too many requests. Please slow down.",
                headers={"Retry-After": str(decision.retry_after_seconds), "X-RateLimit-Limit": str(limit)},
            )
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.retry_after_seconds)
    return _dep


def _safe_ip(value: str) -> str:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return "unknown"
