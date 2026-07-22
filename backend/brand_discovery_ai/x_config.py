"""Environment configuration for the official X API adapter."""

from dataclasses import dataclass, field
import os
import re


class XConfigurationError(ValueError):
    pass


def _enabled(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise XConfigurationError("X_ENABLED must be a boolean.")


@dataclass(frozen=True)
class XSettings:
    enabled: bool = False
    bearer_token: str = field(default="", repr=False)
    timeout_seconds: float = 10.0
    max_results: int = 10
    cache_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "XSettings":
        try:
            timeout = float(os.getenv("X_TIMEOUT_SECONDS", "10"))
            maximum = int(os.getenv("X_MAX_RESULTS", "10"))
            cache_ttl = int(os.getenv("X_CACHE_TTL_SECONDS", "300"))
        except ValueError as exc:
            raise XConfigurationError("X numeric configuration is invalid.") from exc
        return cls(
            enabled=_enabled(os.getenv("X_ENABLED", "false")),
            bearer_token=os.getenv("X_BEARER_TOKEN", "").strip(),
            timeout_seconds=timeout,
            max_results=maximum,
            cache_ttl_seconds=cache_ttl,
        ).validate()

    def validate(self) -> "XSettings":
        if not 1 <= self.timeout_seconds <= 60:
            raise XConfigurationError("X_TIMEOUT_SECONDS must be between 1 and 60.")
        if not 1 <= self.max_results <= 50:
            raise XConfigurationError("X_MAX_RESULTS must be between 1 and 50.")
        if not 1 <= self.cache_ttl_seconds <= 3600:
            raise XConfigurationError("X_CACHE_TTL_SECONDS must be between 1 and 3600.")
        if self.enabled and not self.bearer_token:
            raise XConfigurationError("X_BEARER_TOKEN is required when X is enabled.")
        if len(self.bearer_token) > 4096 or re.search(r"[\x00-\x1f\x7f]", self.bearer_token):
            raise XConfigurationError("X bearer token is invalid.")
        return self
