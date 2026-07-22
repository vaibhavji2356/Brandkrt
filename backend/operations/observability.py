"""Request correlation, safe structured logging, and access metrics."""

from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
import re
import secrets
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .metrics import operational_metrics


_REQUEST_ID = ContextVar("brandkrt_request_id", default="")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SAFE_LOG_FIELDS = {
    "event", "request_id", "method", "route", "status_code", "duration_ms", "role_category",
    "service", "component", "environment", "error_category", "backend", "ready", "operation",
}


def current_request_id() -> str:
    return _REQUEST_ID.get() or "unavailable"


def valid_request_id(value: str | None) -> bool:
    return bool(value and _REQUEST_ID_PATTERN.fullmatch(value))


def configure_structured_logging() -> None:
    environment = os.environ.get("APP_ENV", "development").strip().casefold() or "development"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if environment == "development" else logging.INFO)
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter: logging.Formatter
    if environment in {"production", "prod", "staging"}:
        formatter = SafeJsonFormatter(environment)
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s")
    for handler in root.handlers:
        handler.setFormatter(formatter)
    for noisy in ("uvicorn.access", "multipart.multipart", "watchfiles", "botocore", "boto3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class SafeJsonFormatter(logging.Formatter):
    def __init__(self, environment: str):
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.casefold(),
            "event": getattr(record, "event", "application.log"),
            "message": _bounded_message(record.getMessage()),
            "service": "brandkrt-api",
            "environment": self.environment,
        }
        for key in _SAFE_LOG_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if "request_id" not in payload:
            request_id = current_request_id()
            if request_id != "unavailable":
                payload["request_id"] = request_id
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get("x-request-id")
        request_id = inbound if valid_request_id(inbound) else secrets.token_hex(16)
        request.state.request_id = request_id
        token = _REQUEST_ID.set(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            route = normalized_route(request)
            operational_metrics.record_request(request.method, route, status_code, duration_ms)
            logging.getLogger("brandkrt.access").info("Request completed", extra={
                "event": "http.request.completed", "request_id": request_id,
                "method": request.method, "route": route, "status_code": status_code,
                "duration_ms": duration_ms,
                "role_category": getattr(request.state, "auth_role", "anonymous"),
                "component": "http",
            })
            _REQUEST_ID.reset(token)


def normalized_route(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return str(template)[:200]
    return "/{unmatched}"


def _bounded_message(message: str) -> str:
    lowered = message.casefold()
    sensitive = ("password", "authorization", "cookie", "api_key", "secret", "access_token", "signed_url")
    if any(marker in lowered for marker in sensitive):
        return "Sensitive log message redacted"
    return " ".join(message.split())[:500]
