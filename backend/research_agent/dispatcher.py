"""Backward-compatible Research Dispatcher backed by ProviderOrchestrator."""

from abc import ABC, abstractmethod
import time

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.source_adapters import SourceProvider, build_mock_adapters

from .errors import UnsupportedTaskError
from .metrics import research_metrics
from .models import ResearchTask, TaskResult, TaskStatus, TaskType
from .provider_orchestrator import (
    ProviderOrchestrationResult, ProviderOrchestrator, SUPPORTED_TASK_TYPES,
)


class ResearchExecutionProvider(ABC):
    @abstractmethod
    def supports(self, task: ResearchTask) -> bool: ...

    @abstractmethod
    async def execute(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult: ...


class MockPlatformExecutionProvider(ResearchExecutionProvider):
    """Compatibility wrapper; all execution is delegated to the orchestrator."""

    def __init__(self, adapter: SourceProvider):
        self.adapter = adapter
        self.orchestrator = ProviderOrchestrator([adapter])

    def supports(self, task: ResearchTask) -> bool:
        return task.platform == self.adapter.platform.value and task.type in {
            TaskType.CREATOR_SEARCH, TaskType.BRAND_SEARCH, TaskType.PROFILE_LOOKUP,
            TaskType.KEYWORD_LOOKUP, TaskType.PLATFORM_LOOKUP,
        }

    async def execute(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult:
        if task.type not in SUPPORTED_TASK_TYPES:
            raise UnsupportedTaskError("Research task type is not implemented.")
        result = await self.orchestrator.execute([task], criteria)
        return result.task_results[0]


class ResearchDispatcher:
    def __init__(
        self,
        providers: list[ResearchExecutionProvider] | None = None,
        *,
        orchestrator: ProviderOrchestrator | None = None,
    ):
        self.providers = providers or []
        if orchestrator is None:
            adapters = [
                item.adapter for item in self.providers
                if isinstance(item, MockPlatformExecutionProvider)
            ]
            orchestrator = ProviderOrchestrator(adapters)
        self.orchestrator = orchestrator

    async def dispatch(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult:
        if task.type not in SUPPORTED_TASK_TYPES:
            raise UnsupportedTaskError("Research task type is not implemented.")
        orchestration = await self.dispatch_many([task], criteria)
        if not orchestration.task_results:
            raise UnsupportedTaskError("No research provider supports this task.")
        return orchestration.task_results[0]

    async def dispatch_many(
        self, tasks: list[ResearchTask], criteria: DiscoveryCriteria,
    ) -> ProviderOrchestrationResult:
        if any(task.type not in SUPPORTED_TASK_TYPES for task in tasks):
            raise UnsupportedTaskError("Research task type is not implemented.")
        started = time.perf_counter()
        try:
            result = await self.orchestrator.execute(tasks, criteria)
            completed = sum(
                item.status == TaskStatus.COMPLETED for item in result.task_results
            )
            if completed:
                research_metrics.add("tasks_completed", completed)
            return result
        finally:
            research_metrics.add("dispatcher_time_ms", int((time.perf_counter() - started) * 1000))


def build_mock_dispatcher() -> ResearchDispatcher:
    adapters = build_mock_adapters()
    return ResearchDispatcher(orchestrator=ProviderOrchestrator([
        adapters[platform] for platform in Platform
    ]))
