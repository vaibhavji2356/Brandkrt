import asyncio
from dataclasses import replace
import logging
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from brand_discovery_ai.config import AISettings
from brand_discovery_ai.costing import estimate_request_cost
from brand_discovery_ai.errors import (
    AIDailyBudgetExceededError,
    AIConfigurationError,
    AIIPRateLimitError,
    AIProviderOutputError,
    AIRequestCostLimitError,
    AIUserDailyLimitError,
)
from brand_discovery_ai.evaluation import EVALUATION_RESULT_LIMITS, build_token_calibration
from brand_discovery_ai.metrics import ai_metrics
from brand_discovery_ai.parser import parse_provider_output
from brand_discovery_ai.prompting import build_brand_discovery_prompt
from brand_discovery_ai.providers import (
    BrandDiscoveryProvider,
    MockBrandDiscoveryProvider,
    OpenAIBrandDiscoveryProvider,
    ProviderGeneration,
    build_provider,
    response_json_schema,
)
from brand_discovery_ai.schemas import BrandDiscoveryRequest
from brand_discovery_ai.service import BrandDiscoveryService
from brand_discovery_ai import staging_call
from brand_discovery_ai.staging_call import PaidCallConfirmationError, validate_paid_call_confirmation
from brand_discovery_ai.usage import UsageIdentity, ai_usage_accounting


def _settings(**overrides) -> AISettings:
    values = {
        "provider": "openai",
        "api_key": "sk-test-private-key",
        "model": "gpt-5.6-luna",
        "allowed_models": ("gpt-5.6-luna",),
        "timeout_seconds": 2.0,
        "max_retries": 0,
        "max_output_tokens": 512,
        "max_requests_per_user_per_day": 20,
        "max_requests_per_ip_per_minute": 20,
        "daily_budget_usd": 10.0,
        "max_estimated_cost_per_request_usd": 1.0,
        "mock_mode": False,
    }
    values.update(overrides)
    return AISettings(**values)


def _request() -> BrandDiscoveryRequest:
    return BrandDiscoveryRequest(industry="sustainable fashion", result_limit=1)


def _result(name: str = "Cedar Collective", website: str = "https://cedarcollective.com") -> dict:
    return {
        "brand_name": name,
        "website": website,
        "industry": "Sustainable fashion",
        "description": "AI-generated candidate for creator partnership evaluation.",
        "location": "India",
        "relevance_score": 88,
        "confidence_score": 72,
        "fit_reasons": ["Relevant niche.", "Audience alignment."],
        "outreach_angle": "Suggest a small creator pilot.",
        "source_type": "ai_generated",
        "warnings": ["Verify brand and contact details."],
    }


class _CountingProvider(BrandDiscoveryProvider):
    name = "openai"

    def __init__(self, *, usage: bool = False):
        self.calls = 0
        self.usage = usage

    async def generate(self, *, prompt, request):
        del prompt, request
        self.calls += 1
        payload = {"results": [_result()]}
        if self.usage:
            return ProviderGeneration(payload, input_tokens=321, output_tokens=123, total_tokens=444)
        return payload


@pytest.fixture(autouse=True)
def _reset_in_memory_state():
    ai_usage_accounting.reset()
    ai_metrics.reset()
    yield
    ai_usage_accounting.reset()
    ai_metrics.reset()


@pytest.mark.parametrize(
    ("settings", "reason"),
    [
        (_settings(api_key=""), "missing_api_key"),
        (_settings(model=""), "missing_model"),
        (_settings(model="gpt-5.6-sol"), "unapproved_model"),
        (_settings(allowed_models=("unknown-expensive-model",)), "unsupported_allowed_model"),
    ],
)
def test_openai_configuration_fails_closed(settings, reason):
    with pytest.raises(AIConfigurationError) as exc_info:
        build_provider(settings)
    assert exc_info.value.reason == reason
    if settings.api_key:
        assert settings.api_key not in repr(settings)


def test_mock_mode_isolation_never_builds_openai_provider():
    settings = _settings(api_key="", model="", allowed_models=(), mock_mode=True)
    provider = build_provider(settings)
    assert isinstance(provider, MockBrandDiscoveryProvider)
    with pytest.raises(AIConfigurationError) as exc_info:
        OpenAIBrandDiscoveryProvider(settings)
    assert exc_info.value.reason == "invalid_mock_mode"

    async def scenario():
        mock_service = BrandDiscoveryService(settings, provider)
        await mock_service.preview(_request(), usage_identity=UsageIdentity("user", "127.0.0.1"))

    asyncio.run(scenario())
    assert ai_usage_accounting.snapshot()["reserved_daily_cost_usd"] == 0


def test_per_request_cost_limit_rejects_before_provider_call():
    async def scenario():
        provider = _CountingProvider()
        settings = _settings(max_estimated_cost_per_request_usd=0.000001)
        service = BrandDiscoveryService(settings, provider)
        with pytest.raises(AIRequestCostLimitError):
            await service.preview(_request(), usage_identity=UsageIdentity("user-1", "203.0.113.1"))
        assert provider.calls == 0
        assert ai_metrics.snapshot()["openai"]["budget_rejections"] == 1

    asyncio.run(scenario())


def test_per_user_daily_limit_is_enforced():
    async def scenario():
        provider = _CountingProvider()
        settings = _settings(max_requests_per_user_per_day=1)
        service = BrandDiscoveryService(settings, provider)
        identity = UsageIdentity("user-1", "203.0.113.2")
        await service.preview(_request(), usage_identity=identity)
        with pytest.raises(AIUserDailyLimitError):
            await service.preview(_request(), usage_identity=identity)
        assert provider.calls == 1

    asyncio.run(scenario())


def test_per_ip_minute_limit_is_enforced():
    async def scenario():
        provider = _CountingProvider()
        settings = _settings(max_requests_per_ip_per_minute=1)
        service = BrandDiscoveryService(settings, provider)
        await service.preview(_request(), usage_identity=UsageIdentity("user-1", "203.0.113.3"))
        with pytest.raises(AIIPRateLimitError):
            await service.preview(_request(), usage_identity=UsageIdentity("user-2", "203.0.113.3"))
        assert provider.calls == 1

    asyncio.run(scenario())


def test_daily_budget_uses_retry_inclusive_conservative_reservation():
    async def scenario():
        base = _settings()
        estimate = estimate_request_cost(
            base,
            build_brand_discovery_prompt(_request()),
            response_json_schema(),
        )
        settings = replace(base, daily_budget_usd=estimate.estimated_max_cost_usd * 1.5)
        provider = _CountingProvider()
        service = BrandDiscoveryService(settings, provider)
        await service.preview(_request(), usage_identity=UsageIdentity("user-1", "203.0.113.4"))
        with pytest.raises(AIDailyBudgetExceededError):
            await service.preview(_request(), usage_identity=UsageIdentity("user-2", "203.0.113.5"))
        assert provider.calls == 1

    asyncio.run(scenario())


def test_paid_call_requires_explicit_confirmation_and_openai_mode():
    with pytest.raises(PaidCallConfirmationError):
        validate_paid_call_confirmation(allow_paid_call=False, settings=_settings())
    with pytest.raises(PaidCallConfirmationError):
        validate_paid_call_confirmation(
            allow_paid_call=True,
            settings=_settings(provider="mock", mock_mode=True),
        )


def test_staging_script_without_confirmation_never_runs_provider(monkeypatch):
    called = False

    async def forbidden_call(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not run")

    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_MOCK_MODE", "true")
    monkeypatch.setattr(staging_call, "run_one_paid_call", forbidden_call)
    assert staging_call.main([]) == 2
    assert called is False


def test_duplicate_brand_is_rejected():
    raw = {"results": [_result("Cedar Collective"), _result(" cedar-collective ")]}
    with pytest.raises(AIProviderOutputError):
        parse_provider_output(raw, result_limit=2, provider_name="openai")


@pytest.mark.parametrize(
    "website",
    ["http://cedarcollective.com", "https://127.0.0.1", "https://localhost", "https://brand.example"],
)
def test_unsafe_or_placeholder_website_is_rejected(website):
    with pytest.raises(AIProviderOutputError):
        parse_provider_output(
            {"results": [_result(website=website)]},
            result_limit=1,
            provider_name="openai",
        )


@pytest.mark.parametrize(
    "claim",
    [
        "Based on web research, this brand is confirmed as active.",
        "This brand is externally verified and ready for outreach.",
    ],
)
def test_fabricated_source_claim_is_rejected(claim):
    result = _result()
    result["description"] = claim
    with pytest.raises(AIProviderOutputError):
        parse_provider_output({"results": [result]}, result_limit=1, provider_name="openai")


@pytest.mark.parametrize("mutation", ["placeholder", "scores", "warnings", "reasons", "source"])
def test_additional_provider_quality_failures_are_rejected(mutation):
    result = _result()
    if mutation == "placeholder":
        result["brand_name"] = "Example Brand"
    elif mutation == "scores":
        result["relevance_score"] = 95
        result["confidence_score"] = 5
    elif mutation == "warnings":
        result["warnings"] = [f"Warning {index}" for index in range(5)]
    elif mutation == "reasons":
        result["fit_reasons"] = []
    else:
        result["source_type"] = "web_researched"
    with pytest.raises(AIProviderOutputError):
        parse_provider_output({"results": [result]}, result_limit=1, provider_name="openai")


def test_safe_metrics_include_model_tokens_cost_and_no_secret(caplog):
    async def scenario():
        secret = "sk-test-private-key"
        provider = _CountingProvider(usage=True)
        settings = _settings(api_key=secret)
        caplog.set_level(logging.INFO, logger="brandkrt.ai")
        await BrandDiscoveryService(settings, provider).preview(
            _request(), usage_identity=UsageIdentity("private-user", "203.0.113.6")
        )
        record = ai_metrics.snapshot()["openai"]
        assert record["model"] == "gpt-5.6-luna"
        assert record["actual_input_tokens"] == 321
        assert record["actual_output_tokens"] == 123
        assert record["actual_cost_usd"] > 0
        assert secret not in caplog.text
        assert "private-user" not in caplog.text
        assert "203.0.113.6" not in caplog.text

    asyncio.run(scenario())


def test_token_calibration_has_deterministic_1_5_10_20_fixtures():
    report = build_token_calibration(_settings(max_output_tokens=4000))
    assert tuple(item.result_limit for item in report) == EVALUATION_RESULT_LIMITS
    assert all(item.prompt_tokens > 0 and item.schema_tokens > 0 for item in report)
    assert [item.calibrated_output_tokens for item in report] == sorted(
        item.calibrated_output_tokens for item in report
    )
