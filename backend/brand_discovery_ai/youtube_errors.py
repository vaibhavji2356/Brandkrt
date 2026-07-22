"""Secret-safe errors raised by the YouTube adapter."""


class YouTubeAdapterError(RuntimeError):
    code = "youtube_upstream_error"


class YouTubeDisabledError(YouTubeAdapterError):
    code = "youtube_disabled"


class YouTubeQuotaError(YouTubeAdapterError):
    code = "youtube_quota_exceeded"


class YouTubeTimeoutError(YouTubeAdapterError):
    code = "youtube_timeout"


class YouTubeInvalidKeyError(YouTubeAdapterError):
    code = "youtube_invalid_key"


class YouTubeResponseError(YouTubeAdapterError):
    code = "youtube_invalid_response"
