"""Phase 5+ contracts only. No network, storage, model, or worker implementations."""

from abc import ABC, abstractmethod
from typing import Any

from .models import ResearchTask, TaskResult


class RealPlatformAdapterHook(ABC):
    @abstractmethod
    async def execute_platform_task(self, task: ResearchTask) -> TaskResult: ...


class WebSearchHook(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[dict[str, Any]]: ...


class WebsiteParserHook(ABC):
    @abstractmethod
    async def parse(self, url: str) -> dict[str, Any]: ...


class CRMHook(ABC):
    @abstractmethod
    async def lookup(self, entity_key: str) -> dict[str, Any] | None: ...


class AnalyticsHook(ABC):
    @abstractmethod
    async def measurements(self, entity_key: str) -> dict[str, float]: ...


class EmbeddingsHook(ABC):
    @abstractmethod
    async def encode(self, texts: list[str]) -> list[list[float]]: ...


class VectorSearchHook(ABC):
    @abstractmethod
    async def query(self, vector: list[float], limit: int) -> list[dict[str, Any]]: ...


class BackgroundWorkerHook(ABC):
    @abstractmethod
    async def enqueue(self, task: ResearchTask) -> str: ...
