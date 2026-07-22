"""Deterministic, sequential priority scheduler."""

from .models import ResearchTask

_PRIORITY_ORDER = {"HIGH": 0, "NORMAL": 1, "LOW": 2}


class ResearchScheduler:
    def order(self, tasks: list[ResearchTask]) -> list[ResearchTask]:
        return sorted(tasks, key=lambda task: (
            _PRIORITY_ORDER[task.priority.value], task.created_at, task.id,
        ))
