"""Part 5 — Google OAuth (ID token verification) bridge.

Frontend collects a Google ID token (via Google Identity Services / GIS) and
sends it to POST /api/auth/google. We verify the token against Google's certs
and match-or-create a user. Existing JWT cookie flow remains the source of
truth — Google is only a sign-in entry point.

If GOOGLE_CLIENT_ID is not configured the endpoint cleanly returns 503 so the
rest of the app keeps working with email/password as before.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("brandkrt.oauth")
_google_request = None
_google_request_lock = threading.Lock()


class _CachedGoogleRequest:
    """Reuse Google's HTTP pool and honor certificate cache lifetime.

    Google token verification fetches public signing certificates. Reusing the
    response avoids a network round trip on every login while preserving the
    certificate endpoint's Cache-Control expiry.
    """

    def __init__(self, request) -> None:
        self._request = request
        self._response = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def __call__(self, url, method="GET", body=None, headers=None, timeout=10, **kwargs):
        cacheable = method.upper() == "GET" and "googleapis.com/oauth2" in url
        if not cacheable:
            return self._request(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
        with self._lock:
            if self._response is not None and time.monotonic() < self._expires_at:
                return self._response
            response = self._request(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
            cache_control = response.headers.get("cache-control", "")
            match = re.search(r"max-age=(\d+)", cache_control, re.IGNORECASE)
            ttl = int(match.group(1)) if match else 3600
            self._response = response
            self._expires_at = time.monotonic() + max(60, min(ttl, 21600))
            return response


def _get_google_request(request_class):
    global _google_request
    if _google_request is None:
        with _google_request_lock:
            if _google_request is None:
                _google_request = _CachedGoogleRequest(request_class())
    return _google_request


def get_client_id() -> Optional[str]:
    for env_name in ("GOOGLE_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID", "REACT_APP_GOOGLE_CLIENT_ID"):
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    return None


def is_configured() -> bool:
    return bool(get_client_id())


def verify_google_id_token(token: str) -> dict:
    """Return {email, name, picture, sub, email_verified} or raise HTTPException."""
    client_id = get_client_id()
    if not client_id:
        raise HTTPException(503, "Google sign-in is not configured on this server")
    if not token:
        raise HTTPException(400, "Missing Google credential")
    try:
        from google.oauth2 import id_token as gid_token  # type: ignore
        from google.auth import exceptions as g_exceptions  # type: ignore
        from google.auth.transport import requests as g_requests  # type: ignore
    except Exception as e:  # pragma: no cover
        logger.error("google-auth not installed: %s", e)
        raise HTTPException(503, "Google sign-in dependency missing on server")
    try:
        info = gid_token.verify_oauth2_token(token, _get_google_request(g_requests.Request), client_id)
    except (ValueError, g_exceptions.GoogleAuthError) as e:
        # invalid signature, expired, wrong audience…
        raise HTTPException(401, f"Invalid Google credential: {e}")
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid Google issuer")
    if not info.get("email"):
        raise HTTPException(400, "Google account is missing an email")
    if info.get("email_verified") is not True:
        raise HTTPException(401, "Google account email is not verified")
    return {
        "email": info["email"].lower().strip(),
        "name": info.get("name") or info["email"].split("@")[0],
        "picture": info.get("picture"),
        "sub": info.get("sub"),
        "email_verified": True,
    }
