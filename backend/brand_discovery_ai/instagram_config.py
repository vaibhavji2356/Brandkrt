"""Environment configuration for the official Instagram Graph API adapter."""

from dataclasses import dataclass, field
import os


class InstagramConfigurationError(ValueError):
    pass


def _enabled(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise InstagramConfigurationError("INSTAGRAM_ENABLED must be a boolean.")


@dataclass(frozen=True)
class InstagramSettings:
    enabled: bool = False
    access_token: str = field(default="", repr=False)
    user_id: str = ""
    api_version: str = "v25.0"
    timeout_seconds: float = 10.0
    max_results: int = 12

    @classmethod
    def from_env(cls) -> "InstagramSettings":
        try:
            timeout = float(os.getenv("INSTAGRAM_TIMEOUT_SECONDS", "10"))
            maximum = int(os.getenv("INSTAGRAM_MAX_RESULTS", "12"))
        except ValueError as exc:
            raise InstagramConfigurationError("Instagram numeric configuration is invalid.") from exc
        return cls(
            enabled=_enabled(os.getenv("INSTAGRAM_ENABLED", "false")),
            access_token=os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip(),
            user_id=os.getenv("INSTAGRAM_USER_ID", "").strip(),
            api_version=os.getenv("INSTAGRAM_API_VERSION", "v25.0").strip(),
            timeout_seconds=timeout, max_results=maximum,
        ).validate()

    def validate(self) -> "InstagramSettings":
        if self.enabled and (not self.access_token or not self.user_id):
            raise InstagramConfigurationError(
                "INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID are required when enabled."
            )
        if not self.api_version.startswith("v") or not self.api_version[1:].replace(".", "").isdigit():
            raise InstagramConfigurationError("INSTAGRAM_API_VERSION is invalid.")
        if not 1 <= self.timeout_seconds <= 60:
            raise InstagramConfigurationError("INSTAGRAM_TIMEOUT_SECONDS must be between 1 and 60.")
        if not 1 <= self.max_results <= 50:
            raise InstagramConfigurationError("INSTAGRAM_MAX_RESULTS must be between 1 and 50.")
        return self
