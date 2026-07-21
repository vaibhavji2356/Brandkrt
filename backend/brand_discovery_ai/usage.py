"""Single-process paid-provider request and conservative budget accounting."""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from .config import AISettings
from .errors import (
    AIDailyBudgetExceededError,
    AIIPRateLimitError,
    AIRequestCostLimitError,
    AIUserDailyLimitError,
)


@dataclass(frozen=True)
class UsageIdentity:
    user_id: str
    ip_address: str


class InMemoryAIUsageAccounting:
    """Fail-closed counters scoped to one Python process; no cross-worker coordination."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._day = ""
        self._minute = ""
        self._user_daily_requests: dict[str, int] = {}
        self._ip_minute_requests: dict[str, int] = {}
        self._reserved_daily_cost_usd = 0.0

    def reserve(
        self,
        settings: AISettings,
        identity: UsageIdentity,
        estimated_max_cost_usd: float,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        day = current.strftime("%Y-%m-%d")
        minute = current.strftime("%Y-%m-%dT%H:%M")
        with self._lock:
            self._roll_windows(day, minute)
            if estimated_max_cost_usd > settings.max_estimated_cost_per_request_usd:
                raise AIRequestCostLimitError()
            if self._ip_minute_requests.get(identity.ip_address, 0) >= settings.max_requests_per_ip_per_minute:
                raise AIIPRateLimitError()
            if self._user_daily_requests.get(identity.user_id, 0) >= settings.max_requests_per_user_per_day:
                raise AIUserDailyLimitError()
            if self._reserved_daily_cost_usd + estimated_max_cost_usd > settings.daily_budget_usd:
                raise AIDailyBudgetExceededError()

            self._ip_minute_requests[identity.ip_address] = (
                self._ip_minute_requests.get(identity.ip_address, 0) + 1
            )
            self._user_daily_requests[identity.user_id] = (
                self._user_daily_requests.get(identity.user_id, 0) + 1
            )
            # Reserve the retry-inclusive maximum and never refund it in Phase 3A.
            self._reserved_daily_cost_usd = round(
                self._reserved_daily_cost_usd + estimated_max_cost_usd, 8
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "day": self._day,
                "minute": self._minute,
                "user_daily_requests": dict(self._user_daily_requests),
                "ip_minute_requests": dict(self._ip_minute_requests),
                "reserved_daily_cost_usd": self._reserved_daily_cost_usd,
                "single_process": True,
            }

    def reset(self) -> None:
        with self._lock:
            self._day = ""
            self._minute = ""
            self._user_daily_requests.clear()
            self._ip_minute_requests.clear()
            self._reserved_daily_cost_usd = 0.0

    def _roll_windows(self, day: str, minute: str) -> None:
        if day != self._day:
            self._day = day
            self._user_daily_requests.clear()
            self._reserved_daily_cost_usd = 0.0
        if minute != self._minute:
            self._minute = minute
            self._ip_minute_requests.clear()


ai_usage_accounting = InMemoryAIUsageAccounting()
