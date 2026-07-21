"""Part 5 — Pluggable file storage.

If CLOUDINARY_URL (or the three discrete CLOUDINARY_* env vars) are set, uploads
go to Cloudinary and return a CDN secure_url. Otherwise we fall back to the
legacy local-disk behaviour used in Parts 1-4 so /uploads/{folder}/{file} keeps
working exactly as before in dev.

The public `save_upload()` function returns a *full https URL when on Cloudinary*
and a *relative `/uploads/...` path when on local disk*;
the frontend normalizes those paths to REACT_APP_BACKEND_URL before rendering.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

from upload_security import validate_upload

logger = logging.getLogger("brandkrt.storage")

_CL_READY = False
try:
    if os.environ.get("CLOUDINARY_URL") or os.environ.get("CLOUDINARY_CLOUD_NAME"):
        import cloudinary  # type: ignore
        import cloudinary.uploader  # type: ignore
        if not os.environ.get("CLOUDINARY_URL"):
            cloudinary.config(
                cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
                api_key=os.environ.get("CLOUDINARY_API_KEY"),
                api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
                secure=True,
            )
        _CL_READY = True
        logger.info("storage: Cloudinary enabled")
except Exception as e:  # pragma: no cover
    logger.warning("storage: Cloudinary import failed (%s) — falling back to local disk", e)
    _CL_READY = False


MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "10")) * 1024 * 1024


def provider_name() -> str:
    return "cloudinary" if _CL_READY else "local"


def ensure_local_dir(folder: str, root: Optional[str] = None) -> str:
    root = root or os.environ.get("UPLOAD_ROOT", "./uploads")
    path = os.path.join(root, folder)
    os.makedirs(path, exist_ok=True)
    return path


async def save_upload(*, file_bytes: bytes, original_name: str, folder: str) -> dict:
    """Persist `file_bytes` and return {url, name, kind, size, provider}.

    - folder examples: 'profiles', 'brand_logos', 'products', 'verification',
      'contracts', 'invoices', 'chat'
    """
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        from fastapi import HTTPException
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)}MB limit")

    validated = validate_upload(
        data=file_bytes,
        filename=original_name or "file",
        claimed_type="application/octet-stream",
        folder=folder,
    )
    original_name = validated["filename"]
    kind = validated["kind"]
    ext = original_name.rsplit(".", 1)[-1].lower()

    if _CL_READY:
        # use Cloudinary; resource_type='auto' supports image+raw
        try:
            import cloudinary.uploader as up
            res = up.upload(
                file_bytes,
                folder=f"brandkrt/{folder}",
                resource_type="auto",
                use_filename=False,
                unique_filename=True,
                overwrite=False,
                public_id=secrets.token_hex(10),
            )
            return {
                "url": res.get("secure_url") or res.get("url"),
                "name": original_name,
                "kind": kind,
                "size": len(file_bytes),
                "provider": "cloudinary",
                "public_id": res.get("public_id"),
            }
        except Exception as e:  # pragma: no cover
            logger.warning("Cloudinary upload failed (%s) — using local fallback", e)

    # local fallback
    safe_ext = ext if ext else "bin"
    name = f"{secrets.token_hex(12)}.{safe_ext}"
    abspath = os.path.join(ensure_local_dir(folder), name)
    with open(abspath, "wb") as out:
        out.write(file_bytes)
    return {
        "url": f"/uploads/{folder}/{name}",
        "name": original_name,
        "kind": kind,
        "size": len(file_bytes),
        "provider": "local",
    }
