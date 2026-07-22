"""Environment configuration for the Twitch Helix API adapter."""

from dataclasses import dataclass, field
import os
import re


class TwitchConfigurationError(ValueError):
    pass


def _enabled(value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise TwitchConfigurationError("TWITCH_ENABLED must be a boolean.")


@dataclass(frozen=True)
class TwitchSettings:
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    enabled: bool = False
    timeout_seconds: float = 10.0
    max_results: int = 20
    cache_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "TwitchSettings":
        try:
            timeout = float(os.getenv("TWITCH_TIMEOUT_SECONDS", "10"))
            maximum = int(os.getenv("TWITCH_MAX_RESULTS", "20"))
        except ValueError as exc:
            raise TwitchConfigurationError("Twitch numeric configuration is invalid.") from exc
        return cls(
            client_id=os.getenv("TWITCH_CLIENT_ID", "").strip(),
            client_secret=os.getenv("TWITCH_CLIENT_SECRET", "").strip(),
            enabled=_enabled(os.getenv("TWITCH_ENABLED", "false")),
            timeout_seconds=timeout,
            max_results=maximum,
        ).validate()

    def validate(self) -> "TwitchSettings":
        if not 1 <= self.timeout_seconds <= 60:
            raise TwitchConfigurationError("TWITCH_TIMEOUT_SECONDS must be between 1 and 60.")
        if not 1 <= self.max_results <= 100:
            raise TwitchConfigurationError("TWITCH_MAX_RESULTS must be between 1 and 100.")
        if not 1 <= self.cache_ttl_seconds <= 3600:
            raise TwitchConfigurationError("Twitch cache TTL must be between 1 and 3600.")
        if self.enabled and (not self.client_id or not self.client_secret):
            raise TwitchConfigurationError("Twitch client credentials are required when enabled.")
        for value in (self.client_id, self.client_secret):
            if len(value) > 500 or re.search(r"[\x00-\x1f]", value):
                raise TwitchConfigurationError("Twitch credentials are invalid.")
        return self
