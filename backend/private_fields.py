"""AES-256-GCM envelopes for payout fields; keys never leave the backend."""
import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

FIELDS = {"bank_details", "upi", "details"}
MARKER = "brandkrt_aes256gcm_v1"


def _key():
    raw = os.environ.get("PRIVATE_DATA_ENCRYPTION_KEY", "")
    if not raw:
        if os.environ.get("APP_ENV", "development").lower() == "development":
            return None
        raise HTTPException(503, "Private data encryption is not configured")
    try:
        key = base64.b64decode(raw, validate=True)
        if len(key) != 32:
            raise ValueError()
        return key
    except ValueError:
        raise HTTPException(503, "Private data encryption is not configured") from None


def protect_fields(document):
    result = dict(document)
    for field in FIELDS & result.keys():
        value = result[field]
        if value is None or value == "" or (isinstance(value, dict) and MARKER in value):
            continue
        key = _key()
        if key is None:
            continue
        nonce = os.urandom(12)
        encrypted = AESGCM(key).encrypt(nonce, json.dumps(value).encode(), field.encode())
        result[field] = {MARKER: base64.b64encode(nonce + encrypted).decode()}
    return result


def reveal_field(field, value):
    if not isinstance(value, dict) or MARKER not in value:
        return value  # Legacy records remain readable during migration.
    try:
        key = _key()
        if key is None:
            raise ValueError()
        data = base64.b64decode(value[MARKER], validate=True)
        return json.loads(AESGCM(key).decrypt(data[:12], data[12:], field.encode()))
    except Exception:
        raise HTTPException(503, "Private data is temporarily unavailable") from None
