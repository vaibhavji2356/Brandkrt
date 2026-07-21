"""Environment-backed configuration and fail-closed provider validation."""

from dataclasses import dataclass, field
import math
import os

from .errors import AIConfigurationError


SUPPORTED_MODEL_IDS = frozenset({"gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"})


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AIConfigurationError("invalid_mock_mode")


def _parse_allowed_models(value: str) -> tuple[str, ...]:
    models = tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
    if len(models) > 10 or any(len(model) > 100 for model in models):
        raise AIConfigurationError("invalid_allowed_models")
    return models


@dataclass(frozen=True)
class AISettings:
    provider: str = "mock"
    api_key: str = field(default="", repr=False)
    model: str = ""
    allowed_models: tuple[str, ...] = ()
    timeout_seconds: float = 20.0
    max_retries: int = 1
    max_output_tokens: int = 4000
    max_requests_per_user_per_day: int = 25
    max_requests_per_ip_per_minute: int = 10
    daily_budget_usd: float = 1.0
    max_estimated_cost_per_request_usd: float = 0.06
    mock_mode: bool = True

    @property
    def openai_enabled(self) -> bool:
        return self.provider == "openai" and not self.mock_mode

    def validate(self) -> "AISettings":
        if self.provider not in {"mock", "openai"}:
            raise AIConfigurationError("invalid_provider")
        if not 1 <= self.timeout_seconds <= 60:
            raise AIConfigurationError("invalid_timeout")
        if not 0 <= self.max_retries <= 1:
            raise AIConfigurationError("invalid_retry_limit")
        if not 256 <= self.max_output_tokens <= 8000:
            raise AIConfigurationError("invalid_output_token_limit")
        if not 1 <= self.max_requests_per_user_per_day <= 10_000:
            raise AIConfigurationError("invalid_user_daily_limit")
        if not 1 <= self.max_requests_per_ip_per_minute <= 1_000:
            raise AIConfigurationError("invalid_ip_minute_limit")
        if not _valid_money_limit(self.daily_budget_usd, maximum=100_000):
            raise AIConfigurationError("invalid_daily_budget")
        if not _valid_money_limit(self.max_estimated_cost_per_request_usd, maximum=1_000):
            raise AIConfigurationError("invalid_request_cost_limit")

        if self.openai_enabled:
            if not self.api_key:
                raise AIConfigurationError("missing_api_key")
            if not self.model:
                raise AIConfigurationError("missing_model")
            if not self.allowed_models:
                raise AIConfigurationError("missing_allowed_models")
            unsupported = set(self.allowed_models) - SUPPORTED_MODEL_IDS
            if unsupported:
                raise AIConfigurationError("unsupported_allowed_model")
            if self.model not in self.allowed_models:
                raise AIConfigurationError("unapproved_model")
        return self

    @classmethod
    def from_env(cls) -> "AISettings":
        try:
            settings = cls(
                provider=os.environ.get("AI_PROVIDER", "mock").strip().lower() or "mock",
                api_key=os.environ.get("AI_API_KEY", "").strip(),
                model=os.environ.get("AI_MODEL", "").strip(),
                allowed_models=_parse_allowed_models(os.environ.get("AI_ALLOWED_MODELS", "")),
                timeout_seconds=float(os.environ.get("AI_TIMEOUT_SECONDS", "20")),
                max_retries=int(os.environ.get("AI_MAX_RETRIES", "1")),
                max_output_tokens=int(os.environ.get("AI_MAX_OUTPUT_TOKENS", "4000")),
                max_requests_per_user_per_day=int(
                    os.environ.get("AI_MAX_REQUESTS_PER_USER_PER_DAY", "25")
                ),
                max_requests_per_ip_per_minute=int(
                    os.environ.get("AI_MAX_REQUESTS_PER_IP_PER_MINUTE", "10")
                ),
                daily_budget_usd=float(os.environ.get("AI_DAILY_BUDGET_USD", "1.00")),
                max_estimated_cost_per_request_usd=float(
                    os.environ.get("AI_MAX_ESTIMATED_COST_PER_REQUEST_USD", "0.06")
                ),
                mock_mode=_parse_bool(os.environ.get("AI_MOCK_MODE", "true")),
            )
            if len(settings.model) > 100 or len(settings.api_key) > 1000:
                raise AIConfigurationError("invalid_provider_credentials")
            return settings.validate()
        except AIConfigurationError:
            raise
        except (TypeError, ValueError, OverflowError):
            raise AIConfigurationError("invalid_numeric_setting") from None


def _valid_money_limit(value: float, *, maximum: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and 0 < value <= maximum
