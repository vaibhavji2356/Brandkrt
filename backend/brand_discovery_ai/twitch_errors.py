"""Secret-safe Twitch adapter errors."""


class TwitchAdapterError(RuntimeError):
    code = "twitch_upstream_error"


class TwitchDisabledError(TwitchAdapterError):
    code = "twitch_disabled"


class TwitchInvalidCredentialsError(TwitchAdapterError):
    code = "twitch_invalid_credentials"


class TwitchRateLimitError(TwitchAdapterError):
    code = "twitch_rate_limited"


class TwitchTimeoutError(TwitchAdapterError):
    code = "twitch_timeout"


class TwitchUnavailableError(TwitchAdapterError):
    code = "twitch_unavailable"


class TwitchResponseError(TwitchAdapterError):
    code = "twitch_invalid_response"
