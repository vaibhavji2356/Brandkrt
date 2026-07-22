"""Evidence-specific validation layered on the existing content sniffer."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re

from fastapi import HTTPException

from upload_security import validate_upload


_SUPPORTED = frozenset({"application/pdf", "image/png", "image/jpeg"})
_DANGEROUS_INNER_EXTENSIONS = frozenset({
    "exe", "dll", "com", "msi", "scr", "bat", "cmd", "ps1", "sh", "js", "mjs",
    "html", "htm", "svg", "jar", "zip", "rar", "7z", "docm", "xlsm", "pptm",
})
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


@dataclass(frozen=True)
class ValidatedEvidenceFile:
    display_filename: str
    safe_filename: str
    extension: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    data: bytes


def evidence_max_bytes() -> int:
    try:
        megabytes = int(os.environ.get("EVIDENCE_MAX_UPLOAD_MB", "8"))
    except ValueError:
        megabytes = 8
    return max(1, min(megabytes, 25)) * 1024 * 1024


def validate_evidence_file(data: bytes, filename: str, claimed_type: str) -> ValidatedEvidenceFile:
    maximum = evidence_max_bytes()
    if not data:
        raise HTTPException(status_code=400, detail="Evidence file is empty")
    if len(data) > maximum:
        raise HTTPException(status_code=413, detail=f"Evidence file exceeds {maximum // (1024 * 1024)}MB limit")
    original = (filename or "").strip()
    if not original or "\x00" in original or "/" in original or "\\" in original or ".." in original:
        raise HTTPException(status_code=400, detail="Unsafe evidence filename")
    parts = original.casefold().split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=415, detail="Evidence filename requires a supported extension")
    if any(part in _DANGEROUS_INNER_EXTENSIONS for part in parts[1:-1]):
        raise HTTPException(status_code=415, detail="Double-extension evidence files are not allowed")

    validated = validate_upload(
        data=data, filename=original, claimed_type=claimed_type or "application/octet-stream",
        folder="verification",
    )
    mime_type = validated["content_type"]
    if mime_type not in _SUPPORTED:
        raise HTTPException(status_code=415, detail="Unsupported evidence file type")
    if mime_type == "application/pdf" and b"%%EOF" not in data[-4096:]:
        raise HTTPException(status_code=415, detail="Invalid or incomplete PDF evidence")

    extension = "jpg" if mime_type == "image/jpeg" else ("png" if mime_type == "image/png" else "pdf")
    stem = original.rsplit(".", 1)[0]
    safe_stem = _SAFE_NAME.sub("_", stem).strip(" ._")[:100] or "evidence"
    safe_filename = f"{safe_stem}.{extension}"
    return ValidatedEvidenceFile(
        display_filename=Path(original).name[:200], safe_filename=safe_filename,
        extension=extension, mime_type=mime_type, size_bytes=len(data),
        checksum_sha256=hashlib.sha256(data).hexdigest(), data=data,
    )
