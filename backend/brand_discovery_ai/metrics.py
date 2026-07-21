"""Small in-process AI metrics registry without prompts, payloads, or secrets."""

from collections import defaultdict
from copy import deepcopy
from threading import Lock
from typing import Any


class AIMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: dict[str, dict[str, Any]] = defaultdict(self._new_record)

    @staticmethod
    def _new_record() -> dict[str, Any]:
        return {
            "model": "",
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "retries": 0,
            "timeouts": 0,
            "budget_rejections": 0,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "actual_input_tokens": 0,
            "actual_output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "actual_cost_usd": 0.0,
            "total_duration_ms": 0,
            "last_duration_ms": 0,
        }

    def record_request(
        self,
        provider: str,
        *,
        model: str = "",
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        with self._lock:
            record = self._providers[provider]
            record["model"] = model
            record["requests"] += 1
            record["estimated_input_tokens"] += max(0, estimated_input_tokens)
            record["estimated_output_tokens"] += max(0, estimated_output_tokens)
            record["estimated_cost_usd"] = round(
                record["estimated_cost_usd"] + max(0.0, estimated_cost_usd), 8
            )

    def record_retry(self, provider: str) -> None:
        self._increment(provider, "retries")

    def record_budget_rejection(self, provider: str, *, model: str) -> None:
        with self._lock:
            record = self._providers[provider]
            record["model"] = model
            record["budget_rejections"] += 1

    def record_outcome(
        self,
        provider: str,
        *,
        success: bool,
        duration_ms: int,
        timeout: bool,
        actual_input_tokens: int = 0,
        actual_output_tokens: int = 0,
        actual_cost_usd: float = 0.0,
    ) -> None:
        with self._lock:
            record = self._providers[provider]
            record["successes" if success else "failures"] += 1
            if timeout:
                record["timeouts"] += 1
            record["actual_input_tokens"] += max(0, actual_input_tokens)
            record["actual_output_tokens"] += max(0, actual_output_tokens)
            record["actual_cost_usd"] = round(
                record["actual_cost_usd"] + max(0.0, actual_cost_usd), 8
            )
            record["total_duration_ms"] += duration_ms
            record["last_duration_ms"] = duration_ms

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return deepcopy(dict(self._providers))

    def reset(self) -> None:
        with self._lock:
            self._providers.clear()

    def _increment(self, provider: str, field: str) -> None:
        with self._lock:
            self._providers[provider][field] += 1


ai_metrics = AIMetrics()
