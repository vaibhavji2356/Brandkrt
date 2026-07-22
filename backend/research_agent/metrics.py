"""In-process operational counters; contains no prompts, queries or secrets."""

from dataclasses import asdict, dataclass
from threading import Lock


@dataclass
class ResearchMetricsSnapshot:
    tasks_created: int = 0
    tasks_completed: int = 0
    dispatcher_time_ms: int = 0
    validation_failures: int = 0
    context_size: int = 0
    estimated_tokens: int = 0


class ResearchMetrics:
    def __init__(self):
        self._lock = Lock()
        self._values = ResearchMetricsSnapshot()

    def add(self, field: str, value: int = 1) -> None:
        with self._lock:
            setattr(self._values, field, getattr(self._values, field) + max(0, int(value)))

    def set_gauge(self, field: str, value: int) -> None:
        with self._lock:
            setattr(self._values, field, max(0, int(value)))

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return asdict(self._values)

    def reset(self) -> None:
        with self._lock:
            self._values = ResearchMetricsSnapshot()


research_metrics = ResearchMetrics()
