"""Low-cardinality in-process operational metrics and Prometheus rendering."""

from __future__ import annotations

from collections import Counter
from threading import Lock


class OperationalMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: Counter[tuple[str, str, str]] = Counter()
        self._latency_ms: Counter[tuple[str, str]] = Counter()
        self._latency_count: Counter[tuple[str, str]] = Counter()
        self._counters: Counter[str] = Counter()
        self._evidence_bytes: Counter[str] = Counter()

    def record_request(self, method: str, route: str, status_code: int, duration_ms: float) -> None:
        status_class = f"{max(1, min(5, status_code // 100))}xx"
        key = (method.upper(), route, status_class)
        latency_key = (method.upper(), route)
        with self._lock:
            self._requests[key] += 1
            self._latency_ms[latency_key] += max(0, int(duration_ms))
            self._latency_count[latency_key] += 1

    def increment(self, name: str, value: int = 1) -> None:
        safe_name = "".join(char for char in name.casefold() if char.isalnum() or char == "_")[:80]
        if not safe_name:
            return
        with self._lock:
            self._counters[safe_name] += max(0, int(value))

    def record_evidence_upload(self, size_bytes: int) -> None:
        size = max(0, int(size_bytes))
        bucket = "le_1mb" if size <= 1024 * 1024 else (
            "le_5mb" if size <= 5 * 1024 * 1024 else "gt_5mb"
        )
        with self._lock:
            self._counters["evidence_uploads"] += 1
            self._evidence_bytes[bucket] += size

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "http_request_count": {
                    f"{method} {route} {status}": count
                    for (method, route, status), count in self._requests.items()
                },
                "request_latency_ms_total": {
                    f"{method} {route}": value
                    for (method, route), value in self._latency_ms.items()
                },
                "evidence_upload_bytes": dict(self._evidence_bytes),
            }

    def prometheus(self) -> str:
        lines = [
            "# HELP brandkrt_http_requests_total HTTP requests by normalized route and status class.",
            "# TYPE brandkrt_http_requests_total counter",
        ]
        with self._lock:
            for (method, route, status), count in sorted(self._requests.items()):
                labels = f'method="{_escape(method)}",route="{_escape(route)}",status_class="{status}"'
                lines.append(f"brandkrt_http_requests_total{{{labels}}} {count}")
            lines.extend([
                "# HELP brandkrt_http_request_duration_ms_total Aggregate request duration.",
                "# TYPE brandkrt_http_request_duration_ms_total counter",
            ])
            for (method, route), value in sorted(self._latency_ms.items()):
                labels = f'method="{_escape(method)}",route="{_escape(route)}"'
                lines.append(f"brandkrt_http_request_duration_ms_total{{{labels}}} {value}")
                lines.append(f"brandkrt_http_request_duration_count{{{labels}}} {self._latency_count[(method, route)]}")
            for name, value in sorted(self._counters.items()):
                lines.append(f"brandkrt_{name}_total {value}")
            for bucket, value in sorted(self._evidence_bytes.items()):
                lines.append(f'brandkrt_evidence_upload_bytes_total{{bucket="{bucket}"}} {value}')
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._latency_ms.clear()
            self._latency_count.clear()
            self._counters.clear()
            self._evidence_bytes.clear()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")[:200]


operational_metrics = OperationalMetrics()

