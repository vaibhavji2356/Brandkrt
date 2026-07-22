"""Selectable in-memory and Mongo-backed atomic fixed-window rate limiting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import time

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimitBackendUnavailable(RuntimeError):
    pass


class InMemoryRateLimitBackend:
    name = "memory"
    distributed = False

    def __init__(self, maximum_keys: int = 10_000):
        self.maximum_keys = maximum_keys
        self._lock = asyncio.Lock()
        self._counters: dict[str, tuple[int, int]] = {}

    async def acquire(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now = int(time.time())
        window_id = now // window_seconds
        marker = f"{window_id}:{key}"
        async with self._lock:
            if len(self._counters) >= self.maximum_keys:
                self._counters = {
                    stored: value for stored, value in self._counters.items()
                    if value[0] >= window_id - 1
                }
            _, count = self._counters.get(marker, (window_id, 0))
            retry_after = window_seconds - (now % window_seconds)
            if count >= limit:
                return RateLimitDecision(False, 0, retry_after)
            count += 1
            self._counters[marker] = (window_id, count)
            return RateLimitDecision(True, max(0, limit - count), retry_after)

    async def health_check(self) -> bool:
        return True

    def reset(self) -> None:
        self._counters.clear()


class MongoRateLimitBackend:
    name = "mongo"
    distributed = True

    def __init__(self, database):
        self.collection = database.operational_rate_limits

    async def acquire(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        now_epoch = int(time.time())
        window_id = now_epoch // window_seconds
        digest = hashlib.sha256(f"{window_id}:{key}".encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=window_seconds * 2)
        try:
            document = await self.collection.find_one_and_update(
                {"_id": digest, "$or": [{"count": {"$lt": limit}}, {"count": {"$exists": False}}]},
                {"$inc": {"count": 1}, "$setOnInsert": {
                    "window_id": window_id, "expires_at": expires_at, "created_at": now,
                }},
                upsert=True, return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            document = None
        except PyMongoError as exc:
            raise RateLimitBackendUnavailable("shared rate-limit backend unavailable") from exc
        retry_after = window_seconds - (now_epoch % window_seconds)
        if not document:
            return RateLimitDecision(False, 0, retry_after)
        count = int(document.get("count", limit))
        return RateLimitDecision(True, max(0, limit - count), retry_after)

    async def health_check(self) -> bool:
        try:
            await self.collection.database.command("ping")
            return True
        except Exception as exc:
            raise RateLimitBackendUnavailable("shared rate-limit backend unavailable") from exc


class RateLimiter:
    def __init__(self, backend=None):
        self.backend = backend or InMemoryRateLimitBackend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    async def acquire(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        return await self.backend.acquire(key, limit, window_seconds)

    def configure(self, backend) -> None:
        self.backend = backend


rate_limiter = RateLimiter()


def initialize_rate_limiter(database) -> str:
    backend = os.environ.get("RATE_LIMIT_BACKEND", "memory").strip().casefold() or "memory"
    if backend == "mongo":
        rate_limiter.configure(MongoRateLimitBackend(database))
    elif backend == "memory":
        rate_limiter.configure(InMemoryRateLimitBackend())
    else:
        raise RateLimitBackendUnavailable("unsupported rate-limit backend")
    return rate_limiter.backend_name
