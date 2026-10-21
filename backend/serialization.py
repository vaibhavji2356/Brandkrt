"""Defense in depth for legacy document serializers.

Authorization and explicit public projections remain mandatory; this guard only
prevents authentication material from accidentally reaching any document DTO.
"""
from datetime import datetime
from bson import ObjectId
from private_fields import reveal_field

_SECRETS = {
    "password", "password_hash", "passwordhash", "reset_token", "otp", "otp_code",
    "access_token", "refresh_token", "api_key", "apikey", "client_secret",
    "token", "token_version", "google_sub", "encrypted_token", "encryption_key",
    "jwt_secret", "smtp_password", "private_key", "authorization", "token_hash",
    "internal_notes", "internal_note",
}


def safe_document(value):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in _SECRETS or normalized.endswith(("_secret", "_password", "_token")):
                continue
            result["id" if key == "_id" else key] = safe_document(reveal_field(key, item))
        return result
    if isinstance(value, (list, tuple)):
        return [safe_document(item) for item in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value
