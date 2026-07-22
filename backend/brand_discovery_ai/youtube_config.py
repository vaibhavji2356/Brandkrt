"""Environment configuration for the YouTube Data API v3 adapter."""

from dataclasses import dataclass
import os


class YouTubeConfigurationError(ValueError):
    pass


def _enabled(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise YouTubeConfigurationError("YOUTUBE_ENABLED must be a boolean.")


@dataclass(frozen=True)
class YouTubeSettings:
    api_key: str = ""
    timeout_seconds: float = 10.0
    max_results: int = 10
    enabled: bool = False
    cache_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "YouTubeSettings":
        try:
            timeout = float(os.getenv("YOUTUBE_TIMEOUT_SECONDS", "10"))
            maximum = int(os.getenv("YOUTUBE_MAX_RESULTS", "10"))
        except ValueError as exc:
            raise YouTubeConfigurationError("YouTube numeric configuration is invalid.") from exc
        return cls(
            api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
            timeout_seconds=timeout,
            max_results=maximum,
            enabled=_enabled(os.getenv("YOUTUBE_ENABLED", "false")),
        ).validate()

    def validate(self) -> "YouTubeSettings":
        if not 1 <= self.timeout_seconds <= 60:
            raise YouTubeConfigurationError("YOUTUBE_TIMEOUT_SECONDS must be between 1 and 60.")
        if not 1 <= self.max_results <= 50:
            raise YouTubeConfigurationError("YOUTUBE_MAX_RESULTS must be between 1 and 50.")
        if self.enabled and not self.api_key:
            raise YouTubeConfigurationError("YOUTUBE_API_KEY is required when YouTube is enabled.")
        if not 1 <= self.cache_ttl_seconds <= 3600:
            raise YouTubeConfigurationError("YouTube cache TTL must be between 1 and 3600.")
        return self
