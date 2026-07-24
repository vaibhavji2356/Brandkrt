class InstagramAdapterError(RuntimeError):
    code = "instagram_error"


class InstagramDisabledError(InstagramAdapterError):
    code = "instagram_disabled"


class InstagramAuthenticationError(InstagramAdapterError):
    code = "instagram_authentication"


class InstagramRateLimitError(InstagramAdapterError):
    code = "instagram_rate_limit"


class InstagramResponseError(InstagramAdapterError):
    code = "instagram_response"


class InstagramTimeoutError(InstagramAdapterError):
    code = "instagram_timeout"
