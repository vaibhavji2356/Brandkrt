"""Guardrails, retry, parsing, metrics, and secret-safe provider orchestration."""

import asyncio
from dataclasses import dataclass
import logging
import time

from .config import AISettings
from .costing import CostEstimate, calculate_actual_cost_usd, estimate_request_cost
from .errors import (
    AIProviderOutputError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AIServiceError,
    RetryableProviderError,
)
from .metrics import ai_metrics
from .parser import parse_provider_output
from .prompting import build_brand_discovery_prompt
from .providers import BrandDiscoveryProvider, ProviderGeneration, response_json_schema
from .schemas import BrandDiscoveryPreviewResponse, BrandDiscoveryRequest
from .usage import UsageIdentity, ai_usage_accounting


logger = logging.getLogger("brandkrt.ai")


@dataclass(frozen=True)
class ProviderCallSummary:
    provider: str
    model: str
    duration_ms: int
    retry_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    actual_input_tokens: int
    actual_output_tokens: int
    estimated_max_cost_usd: float
    actual_cost_usd: float


class BrandDiscoveryService:
    def __init__(self, settings: AISettings, provider: BrandDiscoveryProvider) -> None:
        self.settings = settings.validate()
        self.provider = provider
        self.last_call_summary: ProviderCallSummary | None = None

    async def preview(
        self,
        request: BrandDiscoveryRequest,
        *,
        usage_identity: UsageIdentity | None = None,
    ) -> BrandDiscoveryPreviewResponse:
        prompt = build_brand_discovery_prompt(request)
        estimate = self._estimate_and_reserve(prompt, usage_identity)
        total_attempts = self.settings.max_retries + 1
        request_started = time.monotonic()
        model = self.settings.model if self.settings.openai_enabled else "mock"
        ai_metrics.record_request(
            self.provider.name,
            model=model,
            estimated_input_tokens=estimate.estimated_input_tokens if estimate else 0,
            estimated_output_tokens=estimate.estimated_output_tokens if estimate else 0,
            estimated_cost_usd=estimate.estimated_max_cost_usd if estimate else 0.0,
        )
        actual_input_tokens = 0
        actual_output_tokens = 0

        for attempt in range(1, total_attempts + 1):
            try:
                generation = await asyncio.wait_for(
                    self.provider.generate(prompt=prompt, request=request),
                    timeout=self.settings.timeout_seconds,
                )
                raw = generation
                if isinstance(generation, ProviderGeneration):
                    raw = generation.raw_output
                    actual_input_tokens += generation.input_tokens
                    actual_output_tokens += generation.output_tokens
                results = parse_provider_output(
                    raw,
                    result_limit=request.result_limit,
                    provider_name=self.provider.name,
                )
                duration_ms = _elapsed_ms(request_started)
                retry_count = attempt - 1
                actual_cost_usd = calculate_actual_cost_usd(
                    model, actual_input_tokens, actual_output_tokens
                )
                ai_metrics.record_outcome(
                    self.provider.name,
                    success=True,
                    duration_ms=duration_ms,
                    timeout=False,
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                    actual_cost_usd=actual_cost_usd,
                )
                self.last_call_summary = ProviderCallSummary(
                    provider=self.provider.name,
                    model=model,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                    estimated_input_tokens=estimate.estimated_input_tokens if estimate else 0,
                    estimated_output_tokens=estimate.estimated_output_tokens if estimate else 0,
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                    estimated_max_cost_usd=estimate.estimated_max_cost_usd if estimate else 0.0,
                    actual_cost_usd=actual_cost_usd,
                )
                logger.info(
                    "AI preview provider=%s model=%s outcome=success duration_ms=%d retry_count=%d "
                    "timeout=false estimated_input_tokens=%d estimated_output_tokens=%d "
                    "actual_input_tokens=%d actual_output_tokens=%d estimated_cost_usd=%.8f "
                    "actual_cost_usd=%.8f result_count=%d",
                    self.provider.name,
                    model,
                    duration_ms,
                    retry_count,
                    estimate.estimated_input_tokens if estimate else 0,
                    estimate.estimated_output_tokens if estimate else 0,
                    actual_input_tokens,
                    actual_output_tokens,
                    estimate.estimated_max_cost_usd if estimate else 0.0,
                    actual_cost_usd,
                    len(results),
                )
                return BrandDiscoveryPreviewResponse(
                    results=results,
                    count=len(results),
                    provider=self.provider.name,
                    mock_mode=self.provider.is_mock,
                )
            except AIProviderOutputError:
                if attempt < total_attempts:
                    _record_retry(self.provider.name, model, attempt, "invalid_output")
                    continue
                _record_failure(
                    self.provider.name, model, request_started, attempt - 1, "invalid_output",
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                )
                raise
            except AIServiceError:
                _record_failure(
                    self.provider.name, model, request_started, attempt - 1, "service_error",
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                )
                raise
            except asyncio.TimeoutError:
                if attempt < total_attempts:
                    _record_retry(self.provider.name, model, attempt, "timeout")
                    continue
                _record_failure(
                    self.provider.name, model, request_started, attempt - 1, "timeout", timeout=True,
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                )
                raise AIProviderTimeoutError() from None
            except RetryableProviderError:
                if attempt < total_attempts:
                    _record_retry(self.provider.name, model, attempt, "unavailable")
                    continue
                _record_failure(
                    self.provider.name, model, request_started, attempt - 1, "unavailable",
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                )
                raise AIProviderUnavailableError() from None
            except Exception as exc:
                if attempt < total_attempts:
                    _record_retry(self.provider.name, model, attempt, type(exc).__name__)
                    continue
                _record_failure(
                    self.provider.name, model, request_started, attempt - 1, type(exc).__name__,
                    actual_input_tokens=actual_input_tokens,
                    actual_output_tokens=actual_output_tokens,
                )
                raise AIProviderUnavailableError() from None

        raise AIProviderUnavailableError()

    def _estimate_and_reserve(
        self,
        prompt,
        usage_identity: UsageIdentity | None,
    ) -> CostEstimate | None:
        if not self.settings.openai_enabled:
            return None
        estimate = estimate_request_cost(self.settings, prompt, response_json_schema())
        identity = usage_identity or UsageIdentity(user_id="internal", ip_address="internal")
        try:
            ai_usage_accounting.reserve(
                self.settings,
                identity,
                estimate.estimated_max_cost_usd,
            )
        except AIServiceError as exc:
            ai_metrics.record_budget_rejection(
                self.provider.name,
                model=self.settings.model,
            )
            logger.warning(
                "AI preview provider=%s model=%s outcome=budget_rejection reason=%s",
                self.provider.name,
                self.settings.model,
                exc.code,
            )
            raise
        return estimate


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _record_retry(provider: str, model: str, attempt: int, reason: str) -> None:
    ai_metrics.record_retry(provider)
    logger.warning(
        "AI preview provider=%s model=%s outcome=retry retry_count=%d timeout=%s reason=%s",
        provider,
        model,
        attempt,
        str(reason == "timeout").lower(),
        reason,
    )


def _record_failure(
    provider: str,
    model: str,
    started: float,
    retry_count: int,
    reason: str,
    *,
    timeout: bool = False,
    actual_input_tokens: int = 0,
    actual_output_tokens: int = 0,
) -> None:
    duration_ms = _elapsed_ms(started)
    actual_cost_usd = calculate_actual_cost_usd(model, actual_input_tokens, actual_output_tokens)
    ai_metrics.record_outcome(
        provider,
        success=False,
        duration_ms=duration_ms,
        timeout=timeout,
        actual_input_tokens=actual_input_tokens,
        actual_output_tokens=actual_output_tokens,
        actual_cost_usd=actual_cost_usd,
    )
    logger.warning(
        "AI preview provider=%s model=%s outcome=failure duration_ms=%d retry_count=%d "
        "timeout=%s actual_input_tokens=%d actual_output_tokens=%d actual_cost_usd=%.8f reason=%s",
        provider,
        model,
        duration_ms,
        retry_count,
        str(timeout).lower(),
        actual_input_tokens,
        actual_output_tokens,
        actual_cost_usd,
        reason,
    )
