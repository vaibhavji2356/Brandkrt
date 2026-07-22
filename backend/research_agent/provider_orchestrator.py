"""Unified, provider-neutral execution for factual discovery sources."""

import asyncio
from dataclasses import dataclass
import time
from typing import Iterable, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brand_discovery_ai.discovery_schemas import (
    DiscoveryCriteria, NormalizedProfile, Platform,
)
from brand_discovery_ai.source_adapters import SourceProvider

from .models import ResearchTask, TaskResult, TaskStatus, TaskType
from operations.metrics import operational_metrics


SUPPORTED_TASK_TYPES = {
    TaskType.CREATOR_SEARCH, TaskType.BRAND_SEARCH, TaskType.PROFILE_LOOKUP,
    TaskType.KEYWORD_LOOKUP, TaskType.PLATFORM_LOOKUP,
}
HEALTHY_STATUSES = {"ok", "healthy", "ready", "configured"}
DISABLED_STATUSES = {"disabled", "unconfigured"}


class ProviderDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    status: Literal["used", "partial", "failed", "skipped"]
    health_status: str
    tasks_requested: int = Field(ge=0)
    tasks_completed: int = Field(ge=0)
    duration_ms: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class AggregatedProviderResult(BaseModel):
    """Internal attribution wrapper; public normalized schemas remain unchanged."""

    model_config = ConfigDict(extra="forbid")
    provider: str
    platform: Platform
    source: str
    source_confidence: float = Field(ge=0, le=1)
    adjusted_confidence: float = Field(ge=0, le=1)
    entity: NormalizedProfile


class ProviderOrchestrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    providers_used: list[str]
    providers_failed: list[str]
    providers_skipped: list[str]
    warnings: list[str]
    aggregated_results: list[AggregatedProviderResult]
    aggregate_confidence: float = Field(ge=0, le=1)
    provider_diagnostics: list[ProviderDiagnostic]
    task_results: list[TaskResult]


@dataclass
class _ProviderRun:
    provider: str
    bucket: Literal["used", "failed", "skipped"]
    diagnostic: ProviderDiagnostic
    task_results: list[TaskResult]
    attributed: list[AggregatedProviderResult]
    warnings: list[str]


class ProviderOrchestrator:
    """Select, execute, validate and aggregate SourceProvider implementations."""

    def __init__(
        self,
        providers: Iterable[SourceProvider],
        *,
        default_timeout_seconds: float = 15.0,
        provider_timeouts: dict[Platform | str, float] | None = None,
        concurrent: bool = False,
    ):
        if not 0 < default_timeout_seconds <= 120:
            raise ValueError("Provider timeout must be between 0 and 120 seconds.")
        self.default_timeout_seconds = float(default_timeout_seconds)
        self.concurrent = bool(concurrent)
        self.providers: dict[Platform, SourceProvider] = {}
        for provider in providers:
            platform = Platform(provider.platform)
            if platform in self.providers:
                raise ValueError(f"Duplicate provider registration for {platform.value}.")
            self.providers[platform] = provider
        self.provider_timeouts: dict[Platform, float] = {}
        for platform, timeout in (provider_timeouts or {}).items():
            normalized = Platform(platform)
            if not 0 < timeout <= 120:
                raise ValueError("Provider timeout must be between 0 and 120 seconds.")
            self.provider_timeouts[normalized] = float(timeout)

    async def execute(
        self,
        tasks: list[ResearchTask],
        criteria: DiscoveryCriteria,
        *,
        concurrent: bool | None = None,
    ) -> ProviderOrchestrationResult:
        groups = self._group_tasks(tasks)
        use_concurrency = self.concurrent if concurrent is None else bool(concurrent)
        if use_concurrency:
            runs = await asyncio.gather(*[
                self._bounded_provider_run(platform, grouped, criteria)
                for platform, grouped in groups
            ])
        else:
            runs = []
            for platform, grouped in groups:
                runs.append(await self._bounded_provider_run(platform, grouped, criteria))
        attributed = _deduplicate_attributed([
            item for run in runs for item in run.attributed
        ])
        confidence = round(
            sum(item.adjusted_confidence for item in attributed) / len(attributed), 4
        ) if attributed else 0.0
        results_by_id = {
            result.task_id: result for run in runs for result in run.task_results
        }
        return ProviderOrchestrationResult(
            providers_used=_ordered_unique(
                run.provider for run in runs if run.diagnostic.tasks_completed > 0
            ),
            providers_failed=_ordered_unique(run.provider for run in runs if run.bucket == "failed"),
            providers_skipped=_ordered_unique(run.provider for run in runs if run.bucket == "skipped"),
            warnings=_ordered_unique(warning for run in runs for warning in run.warnings),
            aggregated_results=attributed,
            aggregate_confidence=confidence,
            provider_diagnostics=[run.diagnostic for run in runs],
            task_results=[results_by_id[task.id] for task in tasks if task.id in results_by_id],
        )

    def _group_tasks(self, tasks: list[ResearchTask]) -> list[tuple[Platform, list[ResearchTask]]]:
        grouped: dict[Platform, list[ResearchTask]] = {}
        for task in tasks:
            if task.platform is None or task.type not in SUPPORTED_TASK_TYPES:
                continue
            try:
                platform = Platform(task.platform)
            except ValueError:
                continue
            grouped.setdefault(platform, []).append(task)
        return list(grouped.items())

    async def _bounded_provider_run(
        self,
        platform: Platform,
        tasks: list[ResearchTask],
        criteria: DiscoveryCriteria | None = None,
    ) -> _ProviderRun:
        if criteria is None:
            raise ValueError("Discovery criteria are required.")
        timeout = self.provider_timeouts.get(platform, self.default_timeout_seconds)
        try:
            return await asyncio.wait_for(
                self._run_provider(platform, tasks, criteria), timeout=timeout,
            )
        except asyncio.TimeoutError:
            operational_metrics.increment("provider_orchestrator_timeouts")
            warning = f"{platform.value} provider timed out; other providers continued."
            for task in tasks:
                task.status = TaskStatus.FAILED
            return _ProviderRun(
                provider=platform.value, bucket="failed",
                diagnostic=ProviderDiagnostic(
                    provider=platform.value, status="failed", health_status="timeout",
                    tasks_requested=len(tasks), tasks_completed=0,
                    duration_ms=round(timeout * 1000, 2), warnings=[warning],
                ),
                task_results=[TaskResult(
                    task_id=task.id, status=TaskStatus.FAILED, warnings=[warning],
                ) for task in tasks],
                attributed=[], warnings=[warning],
            )

    async def _run_provider(
        self,
        platform: Platform,
        tasks: list[ResearchTask],
        criteria: DiscoveryCriteria,
    ) -> _ProviderRun:
        started = time.perf_counter()
        provider = self.providers.get(platform)
        if provider is None:
            return _skipped_run(
                platform, tasks, "missing",
                f"{platform.value} provider is not registered; provider was skipped.", started,
            )
        try:
            health = await provider.health_check()
        except Exception as error:
            if _is_disabled_error(error):
                return _skipped_run(
                    platform, tasks, "disabled",
                    f"{platform.value} provider is disabled; provider was skipped.", started,
                )
            return _failed_run(
                platform, tasks, "health_error",
                f"{platform.value} provider health check failed safely.", started,
            )
        if not isinstance(health, dict):
            return _failed_run(
                platform, tasks, "invalid_health",
                f"{platform.value} provider returned invalid health diagnostics.", started,
            )
        health_status = str(health.get("status", "unknown")).strip().casefold()
        if health_status in DISABLED_STATUSES:
            return _skipped_run(
                platform, tasks, health_status,
                f"{platform.value} provider is disabled; provider was skipped.", started,
            )
        if health_status not in HEALTHY_STATUSES:
            return _skipped_run(
                platform, tasks, health_status,
                f"{platform.value} provider is unhealthy; provider was skipped.", started,
            )

        task_results: list[TaskResult] = []
        attributed: list[AggregatedProviderResult] = []
        warnings: list[str] = []
        completed = 0
        failures = 0
        for task in tasks:
            if not _supports(provider, task):
                warning = f"{platform.value} provider does not support {task.type.value}; task was skipped."
                task.status = TaskStatus.REJECTED
                task_results.append(TaskResult(
                    task_id=task.id, status=TaskStatus.REJECTED, warnings=[warning],
                ))
                warnings.append(warning)
                continue
            task.status = TaskStatus.RUNNING
            try:
                raw_entities = await _execute_task(provider, task, criteria)
                entities = _validate_entities(provider, raw_entities)
                task.status = TaskStatus.COMPLETED
                completed += 1
                task_results.append(TaskResult(
                    task_id=task.id, status=TaskStatus.COMPLETED, entities=entities,
                ))
                attributed.extend(_attribute(provider, task, entity) for entity in entities)
            except (ValidationError, TypeError, ValueError):
                warning = f"{platform.value} provider returned malformed normalized data."
                task.status = TaskStatus.FAILED
                failures += 1
                task_results.append(TaskResult(
                    task_id=task.id, status=TaskStatus.FAILED, warnings=[warning],
                ))
                warnings.append(warning)
            except Exception as error:
                if _is_disabled_error(error):
                    warning = f"{platform.value} provider became disabled; task was skipped."
                    task.status = TaskStatus.REJECTED
                    task_results.append(TaskResult(
                        task_id=task.id, status=TaskStatus.REJECTED, warnings=[warning],
                    ))
                elif _is_unsupported_error(error):
                    warning = f"{platform.value} provider does not support this operation; task was skipped."
                    task.status = TaskStatus.REJECTED
                    task_results.append(TaskResult(
                        task_id=task.id, status=TaskStatus.REJECTED, warnings=[warning],
                    ))
                else:
                    warning = f"{platform.value} provider failed safely; other providers continued."
                    task.status = TaskStatus.FAILED
                    failures += 1
                    task_results.append(TaskResult(
                        task_id=task.id, status=TaskStatus.FAILED, warnings=[warning],
                    ))
                warnings.append(warning)

        if failures:
            bucket: Literal["used", "failed", "skipped"] = "failed"
            diagnostic_status: Literal["used", "partial", "failed", "skipped"] = "partial" if completed else "failed"
        elif completed:
            bucket = "used"
            diagnostic_status = "used"
        else:
            bucket = "skipped"
            diagnostic_status = "skipped"
        return _ProviderRun(
            provider=platform.value, bucket=bucket,
            diagnostic=ProviderDiagnostic(
                provider=platform.value, status=diagnostic_status,
                health_status=health_status, tasks_requested=len(tasks),
                tasks_completed=completed,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                warnings=_ordered_unique(warnings),
            ),
            task_results=task_results, attributed=attributed,
            warnings=_ordered_unique(warnings),
        )


async def _execute_task(
    provider: SourceProvider, task: ResearchTask, criteria: DiscoveryCriteria,
) -> list[NormalizedProfile]:
    if task.type == TaskType.CREATOR_SEARCH:
        return await provider.search_creators(criteria)
    if task.type == TaskType.BRAND_SEARCH:
        return await provider.search_brands(criteria)
    if task.type in {TaskType.PROFILE_LOOKUP, TaskType.PLATFORM_LOOKUP}:
        profile = await provider.get_profile(task.query)
        return [profile] if profile else []
    if task.type == TaskType.KEYWORD_LOOKUP:
        return (
            await provider.search_brands(criteria)
            if task.entity_type == "brand"
            else await provider.search_creators(criteria)
        )
    raise ValueError("Unsupported research task.")


def _supports(provider: SourceProvider, task: ResearchTask) -> bool:
    capabilities = provider.capabilities
    if task.type == TaskType.BRAND_SEARCH:
        return capabilities.brand_discovery
    if task.type == TaskType.CREATOR_SEARCH:
        return capabilities.creator_discovery
    if task.type == TaskType.KEYWORD_LOOKUP:
        return capabilities.keyword_search and (
            capabilities.brand_discovery if task.entity_type == "brand"
            else capabilities.creator_discovery
        )
    if task.type in {TaskType.PROFILE_LOOKUP, TaskType.PLATFORM_LOOKUP}:
        return capabilities.username_lookup
    return False


def _validate_entities(
    provider: SourceProvider, entities: object,
) -> list[NormalizedProfile]:
    if not isinstance(entities, list):
        raise TypeError("Provider result must be a list.")
    validated = []
    for entity in entities:
        profile = NormalizedProfile.model_validate(entity)
        if profile.platform != provider.platform:
            raise ValueError("Provider returned a mismatched platform.")
        validated.append(profile)
    return validated


def _attribute(
    provider: SourceProvider, task: ResearchTask, entity: NormalizedProfile,
) -> AggregatedProviderResult:
    return AggregatedProviderResult(
        provider=provider.platform.value, platform=entity.platform,
        source=entity.source, source_confidence=entity.source_confidence,
        adjusted_confidence=_adjusted_confidence(entity, task.type), entity=entity,
    )


def _adjusted_confidence(entity: NormalizedProfile, task_type: TaskType) -> float:
    completeness_fields = (
        entity.username, entity.display_name, entity.profile_url, entity.biography,
        entity.location, entity.follower_count, entity.content_count, entity.verified,
    )
    completeness = sum(value is not None for value in completeness_fields) / len(completeness_fields)
    completeness_factor = 0.8 + 0.2 * completeness
    discovery_factor = 1.0 if task_type in {TaskType.PROFILE_LOOKUP, TaskType.PLATFORM_LOOKUP} else 0.9
    return round(entity.source_confidence * completeness_factor * discovery_factor, 4)


def _deduplicate_attributed(
    items: list[AggregatedProviderResult],
) -> list[AggregatedProviderResult]:
    result: list[AggregatedProviderResult] = []
    for item in items:
        keys = _identity_keys(item.entity)
        duplicate_indexes = [
            index for index, current in enumerate(result)
            if keys.intersection(_identity_keys(current.entity))
        ]
        if not duplicate_indexes:
            result.append(item)
            continue
        target = duplicate_indexes[0]
        candidates = [result[index] for index in duplicate_indexes] + [item]
        result[target] = max(
            candidates,
            key=lambda value: (value.adjusted_confidence, value.source_confidence),
        )
        for index in reversed(duplicate_indexes[1:]):
            result.pop(index)
    return result


def _identity_keys(entity: NormalizedProfile) -> set[tuple[str, str, str]]:
    platform = entity.platform.value
    keys = {(platform, "id", entity.platform_id.casefold())}
    if entity.username:
        keys.add((platform, "username", entity.username.lstrip("@").casefold()))
    canonical_url = _canonical_url(entity.profile_url)
    if canonical_url:
        keys.add((platform, "profile_url", canonical_url))
    return keys


def _canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.casefold(), parts.hostname.casefold(), path, "", ""))


def _skipped_run(
    platform: Platform, tasks: list[ResearchTask], health_status: str,
    warning: str, started: float,
) -> _ProviderRun:
    for task in tasks:
        task.status = TaskStatus.REJECTED
    return _ProviderRun(
        provider=platform.value, bucket="skipped",
        diagnostic=ProviderDiagnostic(
            provider=platform.value, status="skipped", health_status=health_status,
            tasks_requested=len(tasks), tasks_completed=0,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            warnings=[warning],
        ),
        task_results=[TaskResult(
            task_id=task.id, status=TaskStatus.REJECTED, warnings=[warning],
        ) for task in tasks],
        attributed=[], warnings=[warning],
    )


def _failed_run(
    platform: Platform, tasks: list[ResearchTask], health_status: str,
    warning: str, started: float,
) -> _ProviderRun:
    for task in tasks:
        task.status = TaskStatus.FAILED
    return _ProviderRun(
        provider=platform.value, bucket="failed",
        diagnostic=ProviderDiagnostic(
            provider=platform.value, status="failed", health_status=health_status,
            tasks_requested=len(tasks), tasks_completed=0,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            warnings=[warning],
        ),
        task_results=[TaskResult(
            task_id=task.id, status=TaskStatus.FAILED, warnings=[warning],
        ) for task in tasks],
        attributed=[], warnings=[warning],
    )


def _is_disabled_error(error: Exception) -> bool:
    return str(getattr(error, "code", "")).casefold().endswith("disabled")


def _is_unsupported_error(error: Exception) -> bool:
    return "unsupported" in str(getattr(error, "code", "")).casefold()


def _ordered_unique(values) -> list[str]:
    return list(dict.fromkeys(values))
