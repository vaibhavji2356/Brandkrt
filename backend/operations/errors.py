"""Stable operational error categories and centralized safe handlers."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .metrics import operational_metrics
from .observability import current_request_id


logger = logging.getLogger("brandkrt.errors")


class StorageOperationError(RuntimeError):
    """Private dependency failure whose vendor details must not cross the API."""

    def __init__(self, code: str = "storage_unavailable"):
        self.code = code
        super().__init__(code)


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        request_id = _request_id(request)
        category = _http_category(error.status_code)
        body = {"detail": error.detail, "code": category, "request_id": request_id}
        headers = dict(error.headers or {})
        headers["X-Request-ID"] = request_id
        return JSONResponse(status_code=error.status_code, content=body, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        request_id = _request_id(request)
        details = [{
            "loc": [str(part) for part in item.get("loc", ())[:8]],
            "msg": str(item.get("msg", "Invalid value"))[:200],
            "type": str(item.get("type", "value_error"))[:100],
        } for item in error.errors()[:20]]
        return JSONResponse(status_code=422, content={
            "detail": details, "code": "validation_error", "request_id": request_id,
        }, headers={"X-Request-ID": request_id})

    @app.exception_handler(StorageOperationError)
    async def storage_error(request: Request, error: StorageOperationError):
        del error
        operational_metrics.increment("storage_operation_failures")
        request_id = _request_id(request)
        return JSONResponse(status_code=503, content={
            "detail": "Private storage is temporarily unavailable.",
            "code": "storage_error", "request_id": request_id,
        }, headers={"X-Request-ID": request_id})

    @app.exception_handler(PyMongoError)
    async def database_error(request: Request, error: PyMongoError):
        del error
        operational_metrics.increment("database_operation_failures")
        request_id = _request_id(request)
        return JSONResponse(status_code=503, content={
            "detail": "The database is temporarily unavailable.",
            "code": "database_error", "request_id": request_id,
        }, headers={"X-Request-ID": request_id})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        request_id = _request_id(request)
        operational_metrics.increment("unhandled_errors")
        if os.environ.get("APP_ENV", "development").casefold() == "development":
            logger.exception("Unhandled request failure", extra={
                "event": "request.unhandled_error", "request_id": request_id,
                "error_category": "internal_error",
            })
        else:
            logger.error("Unhandled request failure class=%s", type(error).__name__, extra={
                "event": "request.unhandled_error", "request_id": request_id,
                "error_category": "internal_error",
            })
        return JSONResponse(status_code=500, content={
            "detail": "An unexpected server error occurred.",
            "code": "internal_error", "request_id": request_id,
        }, headers={"X-Request-ID": request_id})


def _http_category(status_code: int) -> str:
    return {
        400: "validation_error", 401: "authentication_error", 403: "authorization_error",
        404: "not_found", 409: "conflict", 429: "rate_limited",
        502: "dependency_unavailable", 503: "dependency_unavailable", 504: "dependency_timeout",
    }.get(status_code, "validation_error" if status_code < 500 else "internal_error")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or current_request_id()
