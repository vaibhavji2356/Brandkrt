"""Credential-safe errors for the official X API adapter."""


class XAdapterError(RuntimeError):
    code = "x_upstream_error"


class XDisabledError(XAdapterError):
    code = "x_disabled"


class XInvalidTokenError(XAdapterError):
    code = "x_invalid_token"


class XAccessRestrictedError(XAdapterError):
    code = "x_access_restricted"


class XMalformedRequestError(XAdapterError):
    code = "x_malformed_request"


class XNotFoundError(XAdapterError):
    code = "x_not_found"


class XRateLimitError(XAdapterError):
    code = "x_rate_limited"


class XTimeoutError(XAdapterError):
    code = "x_timeout"


class XUnavailableError(XAdapterError):
    code = "x_unavailable"


class XResponseError(XAdapterError):
    code = "x_invalid_response"


class XUnsupportedCapabilityError(XAdapterError):
    code = "x_unsupported_capability"
