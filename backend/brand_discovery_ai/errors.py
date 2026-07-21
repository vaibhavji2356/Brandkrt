"""Public-safe errors used by the Brand Discovery AI boundary."""


class AIServiceError(Exception):
    status_code = 502
    code = "ai_service_error"
    public_message = "Brand discovery is temporarily unavailable."

    def __init__(self) -> None:
        # Never carry provider text or secrets in an exception that reaches FastAPI.
        super().__init__(self.code)


class AIConfigurationError(AIServiceError):
    status_code = 503
    code = "ai_not_configured"
    public_message = "Brand discovery provider configuration is invalid."

    _SAFE_REASONS = {
        "invalid_provider", "invalid_mock_mode", "invalid_timeout", "invalid_retry_limit",
        "invalid_output_token_limit", "invalid_user_daily_limit", "invalid_ip_minute_limit",
        "invalid_daily_budget", "invalid_request_cost_limit", "missing_api_key", "missing_model",
        "missing_allowed_models", "unsupported_allowed_model", "unapproved_model",
        "invalid_allowed_models", "invalid_provider_credentials", "invalid_numeric_setting",
    }

    def __init__(self, reason: str = "invalid_provider") -> None:
        self.reason = reason if reason in self._SAFE_REASONS else "invalid_provider"
        self.code = f"ai_configuration_{self.reason}"
        super().__init__()


class AIUserDailyLimitError(AIServiceError):
    status_code = 429
    code = "ai_user_daily_limit_exceeded"
    public_message = "Daily Brand Discovery request limit reached."


class AIIPRateLimitError(AIServiceError):
    status_code = 429
    code = "ai_ip_rate_limit_exceeded"
    public_message = "Too many Brand Discovery requests. Please try again later."


class AIRequestCostLimitError(AIServiceError):
    status_code = 429
    code = "ai_request_cost_limit_exceeded"
    public_message = "This Brand Discovery request exceeds the configured cost limit."


class AIDailyBudgetExceededError(AIServiceError):
    status_code = 429
    code = "ai_daily_budget_exceeded"
    public_message = "The daily Brand Discovery budget has been reached."


class AIProviderUnavailableError(AIServiceError):
    status_code = 503
    code = "ai_provider_unavailable"
    public_message = "Brand discovery provider is temporarily unavailable."


class AIProviderTimeoutError(AIServiceError):
    status_code = 504
    code = "ai_provider_timeout"
    public_message = "Brand discovery provider timed out."


class AIProviderOutputError(AIServiceError):
    status_code = 502
    code = "ai_invalid_response"
    public_message = "Brand discovery provider returned an invalid response."


class RetryableProviderError(Exception):
    """Internal signal for a transient provider failure; never exposed directly."""
