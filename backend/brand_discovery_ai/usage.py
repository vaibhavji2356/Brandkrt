"""Atomic paid-provider budget reservation with selectable shared accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from threading import Lock

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from .config import AISettings
from .errors import (
    AIAccountingUnavailableError, AIDailyBudgetExceededError, AIIPRateLimitError,
    AIRequestCostLimitError, AIUserDailyLimitError,
)


@dataclass(frozen=True)
class UsageIdentity:
    user_id: str
    ip_address: str


class InMemoryAIUsageAccounting:
    """Atomic within one process; retained only for development and tests."""

    name = "memory"
    distributed = False

    def __init__(self) -> None:
        self._lock = Lock()
        self._day = ""
        self._minute = ""
        self._user_daily_requests: dict[str, int] = {}
        self._ip_minute_requests: dict[str, int] = {}
        self._reserved_daily_cost_usd = 0.0
        self._actual_input_tokens = 0
        self._actual_output_tokens = 0
        self._actual_cost_usd = 0.0

    async def reserve(
        self, settings: AISettings, identity: UsageIdentity, estimated_max_cost_usd: float,
        *, now: datetime | None = None, estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
    ) -> str:
        del estimated_input_tokens, estimated_output_tokens
        current = now or datetime.now(timezone.utc)
        day = current.strftime("%Y-%m-%d")
        minute = current.strftime("%Y-%m-%dT%H:%M")
        with self._lock:
            self._roll_windows(day, minute)
            _validate_request_cost(settings, estimated_max_cost_usd)
            if self._ip_minute_requests.get(identity.ip_address, 0) >= settings.max_requests_per_ip_per_minute:
                raise AIIPRateLimitError()
            if self._user_daily_requests.get(identity.user_id, 0) >= settings.max_requests_per_user_per_day:
                raise AIUserDailyLimitError()
            if self._reserved_daily_cost_usd + estimated_max_cost_usd > settings.daily_budget_usd:
                raise AIDailyBudgetExceededError()
            self._ip_minute_requests[identity.ip_address] = self._ip_minute_requests.get(identity.ip_address, 0) + 1
            self._user_daily_requests[identity.user_id] = self._user_daily_requests.get(identity.user_id, 0) + 1
            self._reserved_daily_cost_usd = round(self._reserved_daily_cost_usd + estimated_max_cost_usd, 8)
        return secrets.token_hex(16)

    async def record_actual(
        self, reservation_id: str, *, input_tokens: int, output_tokens: int,
        actual_cost_usd: float, success: bool,
    ) -> None:
        del reservation_id, success
        with self._lock:
            self._actual_input_tokens += max(0, int(input_tokens))
            self._actual_output_tokens += max(0, int(output_tokens))
            self._actual_cost_usd = round(self._actual_cost_usd + max(0.0, actual_cost_usd), 8)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "backend": self.name, "distributed": self.distributed,
                "day": self._day, "minute": self._minute,
                "user_daily_requests": dict(self._user_daily_requests),
                "ip_minute_requests": dict(self._ip_minute_requests),
                "reserved_daily_cost_usd": self._reserved_daily_cost_usd,
                "actual_input_tokens": self._actual_input_tokens,
                "actual_output_tokens": self._actual_output_tokens,
                "actual_cost_usd": self._actual_cost_usd,
                "single_process": True,
            }

    def reset(self) -> None:
        with self._lock:
            self._day = self._minute = ""
            self._user_daily_requests.clear()
            self._ip_minute_requests.clear()
            self._reserved_daily_cost_usd = 0.0
            self._actual_input_tokens = self._actual_output_tokens = 0
            self._actual_cost_usd = 0.0

    async def health_check(self) -> bool:
        return True

    def _roll_windows(self, day: str, minute: str) -> None:
        if day != self._day:
            self._day = day
            self._user_daily_requests.clear()
            self._reserved_daily_cost_usd = 0.0
        if minute != self._minute:
            self._minute = minute
            self._ip_minute_requests.clear()


class MongoAIUsageAccounting:
    """Atlas transaction-backed reservation across global, user, and IP counters."""

    name = "mongo"
    distributed = True

    def __init__(self, database):
        self.database = database
        self.client = database.client
        self.counters = database.ai_usage_counters
        self.reservations = database.ai_usage_reservations

    async def reserve(
        self, settings: AISettings, identity: UsageIdentity, estimated_max_cost_usd: float,
        *, now: datetime | None = None, estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
    ) -> str:
        _validate_request_cost(settings, estimated_max_cost_usd)
        current = now or datetime.now(timezone.utc)
        day = current.strftime("%Y-%m-%d")
        minute = current.strftime("%Y-%m-%dT%H:%M")
        reservation_id = secrets.token_hex(16)
        cost_units = max(0, round(estimated_max_cost_usd * 100_000_000))
        budget_units = round(settings.daily_budget_usd * 100_000_000)
        user_hash = _identity_hash(identity.user_id)
        ip_hash = _identity_hash(identity.ip_address)
        expires_at = current + timedelta(days=8)
        try:
            async with await self.client.start_session() as session:
                async with session.start_transaction():
                    await self._increment(
                        f"global:{day}", "reserved_cost_units", cost_units, budget_units,
                        current, expires_at, session, AIDailyBudgetExceededError,
                    )
                    await self._increment(
                        f"user:{day}:{user_hash}", "request_count", 1,
                        settings.max_requests_per_user_per_day, current, expires_at, session,
                        AIUserDailyLimitError,
                    )
                    await self._increment(
                        f"ip:{minute}:{ip_hash}", "request_count", 1,
                        settings.max_requests_per_ip_per_minute, current,
                        current + timedelta(minutes=2), session, AIIPRateLimitError,
                    )
                    await self.reservations.insert_one({
                        "_id": reservation_id, "day": day, "estimated_cost_units": cost_units,
                        "estimated_input_tokens": max(0, int(estimated_input_tokens)),
                        "estimated_output_tokens": max(0, int(estimated_output_tokens)),
                        "actual_input_tokens": 0, "actual_output_tokens": 0,
                        "actual_cost_units": 0, "outcome": "reserved",
                        "created_at": current, "expires_at": expires_at,
                    }, session=session)
        except (AIRequestCostLimitError, AIDailyBudgetExceededError, AIUserDailyLimitError, AIIPRateLimitError):
            raise
        except (PyMongoError, NotImplementedError, AttributeError, TypeError) as exc:
            raise AIAccountingUnavailableError() from exc
        return reservation_id

    async def record_actual(
        self, reservation_id: str, *, input_tokens: int, output_tokens: int,
        actual_cost_usd: float, success: bool,
    ) -> None:
        try:
            await self.reservations.update_one(
                {"_id": reservation_id, "outcome": "reserved"},
                {"$set": {
                    "actual_input_tokens": max(0, int(input_tokens)),
                    "actual_output_tokens": max(0, int(output_tokens)),
                    "actual_cost_units": max(0, round(actual_cost_usd * 100_000_000)),
                    "outcome": "success" if success else "failed",
                    "completed_at": datetime.now(timezone.utc),
                }},
            )
        except PyMongoError as exc:
            raise AIAccountingUnavailableError() from exc

    async def _increment(
        self, counter_id: str, field: str, amount: int, maximum: int,
        now: datetime, expires_at: datetime, session, error_type,
    ) -> None:
        try:
            document = await self.counters.find_one_and_update(
                {"_id": counter_id, "$or": [{field: {"$lte": maximum - amount}}, {field: {"$exists": False}}]},
                {"$inc": {field: amount}, "$setOnInsert": {"created_at": now, "expires_at": expires_at}},
                upsert=True, return_document=ReturnDocument.AFTER, session=session,
            )
        except DuplicateKeyError:
            document = None
        if not document:
            raise error_type()

    async def health_check(self) -> bool:
        try:
            await self.database.command("ping")
            return True
        except Exception as exc:
            raise AIAccountingUnavailableError() from exc

    def snapshot(self) -> dict[str, object]:
        return {"backend": self.name, "distributed": True, "shared_state": "mongo"}

    def reset(self) -> None:
        # Production shared counters are intentionally never reset by process code.
        return None


class AIUsageAccounting:
    def __init__(self):
        self.backend = InMemoryAIUsageAccounting()

    async def reserve(self, *args, **kwargs) -> str:
        return await self.backend.reserve(*args, **kwargs)

    async def record_actual(self, *args, **kwargs) -> None:
        await self.backend.record_actual(*args, **kwargs)

    async def health_check(self) -> bool:
        return await self.backend.health_check()

    def configure(self, backend) -> None:
        self.backend = backend

    def snapshot(self) -> dict[str, object]:
        return self.backend.snapshot()

    def reset(self) -> None:
        self.backend.reset()


def initialize_ai_usage_accounting(database) -> str:
    backend = os.environ.get("AI_USAGE_BACKEND", "memory").strip().casefold() or "memory"
    if backend == "mongo":
        ai_usage_accounting.configure(MongoAIUsageAccounting(database))
    elif backend == "memory":
        ai_usage_accounting.configure(InMemoryAIUsageAccounting())
    else:
        raise AIAccountingUnavailableError()
    return backend


def _validate_request_cost(settings: AISettings, estimated_cost: float) -> None:
    if estimated_cost > settings.max_estimated_cost_per_request_usd:
        raise AIRequestCostLimitError()


def _identity_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


ai_usage_accounting = AIUsageAccounting()
