"""Provider-independent task dispatch; execution providers own adapter details."""

from abc import ABC, abstractmethod
import time

from brand_discovery_ai.discovery_schemas import DiscoveryCriteria, Platform
from brand_discovery_ai.source_adapters import SourceProvider, build_mock_adapters

from .errors import UnsupportedTaskError
from .metrics import research_metrics
from .models import ResearchTask, TaskResult, TaskStatus, TaskType


class ResearchExecutionProvider(ABC):
    @abstractmethod
    def supports(self, task: ResearchTask) -> bool: ...

    @abstractmethod
    async def execute(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult: ...


class MockPlatformExecutionProvider(ResearchExecutionProvider):
    """The only implemented bridge; invokes deterministic adapters without transport."""

    def __init__(self, adapter: SourceProvider):
        self.adapter = adapter

    def supports(self, task: ResearchTask) -> bool:
        return task.platform == self.adapter.platform.value and task.type in {
            TaskType.CREATOR_SEARCH, TaskType.BRAND_SEARCH, TaskType.PROFILE_LOOKUP,
            TaskType.KEYWORD_LOOKUP, TaskType.PLATFORM_LOOKUP,
        }

    async def execute(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult:
        if task.type == TaskType.CREATOR_SEARCH:
            entities = await self.adapter.search_creators(criteria)
        elif task.type == TaskType.BRAND_SEARCH:
            entities = await self.adapter.search_brands(criteria)
        elif task.type in {TaskType.PROFILE_LOOKUP, TaskType.PLATFORM_LOOKUP}:
            profile = await self.adapter.get_profile(task.query)
            entities = [profile] if profile else []
        elif task.type == TaskType.KEYWORD_LOOKUP:
            entities = (
                await self.adapter.search_brands(criteria)
                if task.entity_type == "brand"
                else await self.adapter.search_creators(criteria)
            )
        else:
            raise UnsupportedTaskError("Research task type is not implemented.")
        return TaskResult(task_id=task.id, status=TaskStatus.COMPLETED, entities=entities)


class ResearchDispatcher:
    def __init__(self, providers: list[ResearchExecutionProvider]):
        self.providers = providers

    async def dispatch(self, task: ResearchTask, criteria: DiscoveryCriteria) -> TaskResult:
        started = time.perf_counter()
        try:
            provider = next((item for item in self.providers if item.supports(task)), None)
            if provider is None:
                raise UnsupportedTaskError("No research provider supports this task.")
            task.status = TaskStatus.RUNNING
            result = await provider.execute(task, criteria)
            task.status = result.status
            if result.status == TaskStatus.COMPLETED:
                research_metrics.add("tasks_completed")
            return result
        finally:
            research_metrics.add("dispatcher_time_ms", int((time.perf_counter() - started) * 1000))


def build_mock_dispatcher() -> ResearchDispatcher:
    adapters = build_mock_adapters()
    return ResearchDispatcher([
        MockPlatformExecutionProvider(adapters[platform]) for platform in Platform
    ])
