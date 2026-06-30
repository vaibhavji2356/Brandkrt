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
from collections import defaultdict, deque
from typing import Iterable, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

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
_RL_BUCKETS: "defaultdict[str, deque[float]]" = defaultdict(deque)


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
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limiter_dependency(action: str, limit: int = 10, window: int = 60):
    """FastAPI Depends() factory. Use:  Depends(limiter_dependency('register', 5, 300))"""
    async def _dep(request: Request) -> None:
        rate_limit(f"{action}:{client_ip(request)}", limit=limit, window=window)
    return _dep
