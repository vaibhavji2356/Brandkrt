"""Secret-safe, environment-aware production configuration validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from urllib.parse import urlsplit


PRODUCTION_ENVIRONMENTS = {"production", "prod", "staging"}
_PLACEHOLDER_MARKERS = (
    "replace_", "replace-", "change_me", "change-me", "changeme", "your_", "your-",
    "example", "placeholder", "secret_here", "password_here", "user:pass@",
)


@dataclass(frozen=True)
class ConfigurationIssue:
    code: str
    setting: str


@dataclass(frozen=True)
class ConfigurationReport:
    environment: str
    production: bool
    valid: bool
    errors: tuple[ConfigurationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[ConfigurationIssue, ...] = field(default_factory=tuple)
    features: dict[str, str | bool] = field(default_factory=dict)

    def public(self) -> dict:
        data = asdict(self)
        data["errors"] = [asdict(item) for item in self.errors]
        data["warnings"] = [asdict(item) for item in self.warnings]
        return data


class ProductionConfigurationError(RuntimeError):
    def __init__(self, report: ConfigurationReport):
        self.report = report
        codes = ",".join(item.code for item in report.errors) or "invalid_configuration"
        super().__init__(f"Production configuration validation failed: {codes}")


def validate_configuration(environment: dict[str, str] | None = None) -> ConfigurationReport:
    values = environment if environment is not None else os.environ
    app_env = _value(values, "APP_ENV", "development").casefold()
    production = app_env in PRODUCTION_ENVIRONMENTS
    errors: list[ConfigurationIssue] = []
    warnings: list[ConfigurationIssue] = []

    for key in ("MONGO_URL", "DB_NAME", "JWT_SECRET"):
        if not _value(values, key):
            errors.append(ConfigurationIssue("missing_required_setting", key))

    mongo_url = _value(values, "MONGO_URL")
    if production and mongo_url and "USER:PASS@" in mongo_url.upper():
        errors.append(ConfigurationIssue("placeholder_database_configuration", "MONGO_URL"))

    jwt_secret = _value(values, "JWT_SECRET")
    if jwt_secret and (_placeholder(jwt_secret) or (production and len(jwt_secret) < 32)):
        errors.append(ConfigurationIssue("weak_or_placeholder_secret", "JWT_SECRET"))
    admin_password = _value(values, "ADMIN_PASSWORD")
    if production and admin_password and (_placeholder(admin_password) or len(admin_password) < 12):
        errors.append(ConfigurationIssue("weak_or_placeholder_secret", "ADMIN_PASSWORD"))

    debug = _truthy(_value(values, "DEBUG", _value(values, "APP_DEBUG", "false")))
    if production and debug:
        errors.append(ConfigurationIssue("debug_enabled_in_production", "DEBUG"))

    origins = [item.strip().rstrip("/") for item in _value(values, "CORS_ORIGINS").split(",") if item.strip()]
    if production and not origins:
        errors.append(ConfigurationIssue("missing_production_origins", "CORS_ORIGINS"))
    for origin in origins:
        parsed = urlsplit(origin)
        if "*" in origin or parsed.path not in {"", "/"} or not parsed.netloc:
            errors.append(ConfigurationIssue("invalid_cors_origin", "CORS_ORIGINS"))
            break
        if production and parsed.scheme != "https":
            errors.append(ConfigurationIssue("insecure_production_origin", "CORS_ORIGINS"))
            break

    storage_provider = _value(values, "EVIDENCE_STORAGE_PROVIDER", "local").casefold()
    evidence_enabled = _truthy(_value(values, "EVIDENCE_UPLOAD_ENABLED", "true"))
    if storage_provider not in {"local", "s3"}:
        errors.append(ConfigurationIssue("unsupported_storage_provider", "EVIDENCE_STORAGE_PROVIDER"))
    if production and evidence_enabled and storage_provider == "local":
        errors.append(ConfigurationIssue("ephemeral_local_evidence_storage", "EVIDENCE_STORAGE_PROVIDER"))
    if storage_provider == "s3":
        for key in (
            "EVIDENCE_STORAGE_BUCKET", "EVIDENCE_STORAGE_REGION",
            "EVIDENCE_STORAGE_ACCESS_KEY", "EVIDENCE_STORAGE_SECRET_KEY",
        ):
            value = _value(values, key)
            if not value:
                errors.append(ConfigurationIssue("missing_storage_setting", key))
            elif key.endswith(("ACCESS_KEY", "SECRET_KEY")) and _placeholder(value):
                errors.append(ConfigurationIssue("placeholder_storage_credential", key))
        ttl = _integer(values, "EVIDENCE_STORAGE_SIGNED_URL_TTL_SECONDS", 300)
        if ttl < 30 or ttl > 3600:
            errors.append(ConfigurationIssue("unsafe_signed_url_ttl", "EVIDENCE_STORAGE_SIGNED_URL_TTL_SECONDS"))
        encryption = _value(values, "EVIDENCE_STORAGE_ENCRYPTION_MODE", "AES256")
        if encryption not in {"AES256", "aws:kms"}:
            errors.append(ConfigurationIssue("invalid_storage_encryption", "EVIDENCE_STORAGE_ENCRYPTION_MODE"))
        if encryption == "aws:kms" and not _value(values, "EVIDENCE_STORAGE_KMS_KEY_ID"):
            errors.append(ConfigurationIssue("missing_storage_kms_key", "EVIDENCE_STORAGE_KMS_KEY_ID"))

    limiter_backend = _value(values, "RATE_LIMIT_BACKEND", "memory").casefold()
    if limiter_backend not in {"memory", "mongo"}:
        errors.append(ConfigurationIssue("unsupported_rate_limit_backend", "RATE_LIMIT_BACKEND"))
    if production and limiter_backend != "mongo":
        errors.append(ConfigurationIssue("non_distributed_rate_limit_backend", "RATE_LIMIT_BACKEND"))

    ai_backend = _value(values, "AI_USAGE_BACKEND", "memory").casefold()
    paid_ai = _value(values, "AI_PROVIDER", "mock").casefold() == "openai" and not _truthy(
        _value(values, "AI_MOCK_MODE", "true")
    )
    if ai_backend not in {"memory", "mongo"}:
        errors.append(ConfigurationIssue("unsupported_ai_usage_backend", "AI_USAGE_BACKEND"))
    if production and paid_ai and ai_backend != "mongo":
        errors.append(ConfigurationIssue("non_distributed_ai_usage_backend", "AI_USAGE_BACKEND"))
    if paid_ai:
        key = _value(values, "AI_API_KEY")
        if not key or _placeholder(key):
            errors.append(ConfigurationIssue("missing_paid_ai_key", "AI_API_KEY"))

    admin_lead_mock_mode = _truthy(_value(values, "ADMIN_LEAD_MOCK_MODE", "false"))
    if production and admin_lead_mock_mode:
        errors.append(ConfigurationIssue("admin_lead_mock_mode_in_production", "ADMIN_LEAD_MOCK_MODE"))

    if not production and storage_provider == "local":
        warnings.append(ConfigurationIssue("development_local_storage", "EVIDENCE_STORAGE_PROVIDER"))
    if not production and limiter_backend == "memory":
        warnings.append(ConfigurationIssue("development_memory_rate_limits", "RATE_LIMIT_BACKEND"))

    return ConfigurationReport(
        environment=app_env,
        production=production,
        valid=not errors,
        errors=tuple(_unique(errors)),
        warnings=tuple(_unique(warnings)),
        features={
            "evidence_upload_enabled": evidence_enabled,
            "storage_provider": storage_provider,
            "rate_limit_backend": limiter_backend,
            "ai_usage_backend": ai_backend,
            "paid_ai_enabled": paid_ai,
            "admin_lead_mock_mode": admin_lead_mock_mode,
        },
    )


def require_valid_configuration(environment: dict[str, str] | None = None) -> ConfigurationReport:
    report = validate_configuration(environment)
    if not report.valid:
        raise ProductionConfigurationError(report)
    return report


require_valid_production_configuration = require_valid_configuration


def _value(values, key: str, default: str = "") -> str:
    return str(values.get(key, default) or "").strip().strip("'\"")


def _truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


def _placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _integer(values, key: str, default: int) -> int:
    try:
        return int(_value(values, key, str(default)))
    except ValueError:
        return -1


def _unique(items: list[ConfigurationIssue]) -> list[ConfigurationIssue]:
    seen = set()
    output = []
    for item in items:
        marker = (item.code, item.setting)
        if marker not in seen:
            seen.add(marker)
            output.append(item)
    return output
