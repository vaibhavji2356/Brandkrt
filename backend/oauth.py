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
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("brandkrt.oauth")


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
        from google.auth.transport import requests as g_requests  # type: ignore
    except Exception as e:  # pragma: no cover
        logger.error("google-auth not installed: %s", e)
        raise HTTPException(503, "Google sign-in dependency missing on server")
    try:
        info = gid_token.verify_oauth2_token(token, g_requests.Request(), client_id)
    except ValueError as e:
        # invalid signature, expired, wrong audience…
        raise HTTPException(401, f"Invalid Google credential: {e}")
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(401, "Invalid Google issuer")
    if not info.get("email"):
        raise HTTPException(400, "Google account is missing an email")
    return {
        "email": info["email"].lower().strip(),
        "name": info.get("name") or info["email"].split("@")[0],
        "picture": info.get("picture"),
        "sub": info.get("sub"),
        "email_verified": bool(info.get("email_verified", True)),
    }
