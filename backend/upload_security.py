"""Content-based validation for user uploads.

Client filenames and Content-Type headers are treated only as hints. The
detected media type returned here is the value persisted and served by the API.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError


_TYPE_EXTENSIONS: Dict[str, set[str]] = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/gif": {"gif"},
    "image/webp": {"webp"},
    "image/avif": {"avif"},
    "application/pdf": {"pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"xlsx"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {"pptx"},
    "text/plain": {"txt"},
    "text/csv": {"csv"},
}

_FOLDER_TYPES: Dict[str, set[str]] = {
    "profiles": {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"},
    "brand_logos": {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"},
    "products": {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"},
    "verification": {"image/jpeg", "image/png", "image/webp", "application/pdf"},
    "contracts": {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "invoices": {
        "image/jpeg", "image/png", "image/webp", "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
    "chat": set(_TYPE_EXTENSIONS),
}

_EXECUTABLE_PREFIXES: Tuple[bytes, ...] = (
    b"MZ",  # Windows PE
    b"\x7fELF",
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",  # Mach-O
    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    b"#!",
)
_DANGEROUS_ARCHIVE_SUFFIXES = {
    ".exe", ".dll", ".com", ".msi", ".scr", ".bat", ".cmd", ".ps1",
    ".sh", ".js", ".mjs", ".html", ".htm", ".svg", ".jar",
}
_PIL_FORMATS = {
    "image/jpeg": {"JPEG"},
    "image/png": {"PNG"},
    "image/gif": {"GIF"},
    "image/webp": {"WEBP"},
    "image/avif": {"AVIF"},
}
_DECLARED_ALIASES = {
    "image/jpeg": {"image/jpg", "image/pjpeg"},
    "text/csv": {"text/plain", "application/csv", "application/vnd.ms-excel"},
    "text/plain": {"application/text"},
}


def _verify_image(data: bytes, media_type: str) -> str:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in _PIL_FORMATS[media_type]:
                raise HTTPException(415, "Image format does not match file content")
            if image.width * image.height > 40_000_000:
                raise HTTPException(413, "Image dimensions are too large")
            image.verify()
    except HTTPException:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise HTTPException(415, "Invalid or corrupted image")
    return media_type


def _reject_executable_content(data: bytes) -> None:
    prefix = data[:16].lstrip()
    if any(prefix.startswith(marker) for marker in _EXECUTABLE_PREFIXES):
        raise HTTPException(415, "Executable uploads are not allowed")
    lowered = data[:4096].lstrip().lower()
    if lowered.startswith((b"<svg", b"<?xml")) and b"<svg" in lowered:
        raise HTTPException(415, "SVG uploads are not allowed")
    if lowered.startswith((b"<html", b"<!doctype html", b"<script")):
        raise HTTPException(415, "Executable web content is not allowed")


def _detect_office_zip(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [name.lower() for name in archive.namelist()]
    except (zipfile.BadZipFile, OSError, ValueError):
        raise HTTPException(415, "Invalid office document")

    if not names or "[content_types].xml" not in names:
        raise HTTPException(415, "Generic ZIP uploads are not allowed")
    if any(
        name.endswith(tuple(_DANGEROUS_ARCHIVE_SUFFIXES))
        or name.endswith("vbaproject.bin")
        or "/embeddings/" in name
        for name in names
    ):
        raise HTTPException(415, "Documents containing executable or embedded content are not allowed")
    if any(name.startswith("word/") for name in names):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if any(name.startswith("xl/") for name in names):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if any(name.startswith("ppt/") for name in names):
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    raise HTTPException(415, "Unsupported office document")


def _detect_type(data: bytes, extension: str) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return _verify_image(data, "image/jpeg")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return _verify_image(data, "image/png")
    if data.startswith((b"GIF87a", b"GIF89a")):
        return _verify_image(data, "image/gif")
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return _verify_image(data, "image/webp")
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in {b"avif", b"avis", b"mif1"}:
        return _verify_image(data, "image/avif")
    if data.startswith(b"%PDF-"):
        lowered = data.lower()
        if any(marker in lowered for marker in (b"/javascript", b"/js ", b"/launch", b"/embeddedfile")):
            raise HTTPException(415, "Active or embedded PDF content is not allowed")
        return "application/pdf"
    if data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return _detect_office_zip(data)
    if extension in {"txt", "csv"}:
        if b"\x00" in data:
            raise HTTPException(415, "Binary content is not allowed in text uploads")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Text uploads must be UTF-8")
        if re.search(r"<\s*(?:script|svg|html|iframe)\b", text, re.IGNORECASE):
            raise HTTPException(415, "Executable web content is not allowed")
        return "text/csv" if extension == "csv" else "text/plain"
    raise HTTPException(415, "Unsupported or unrecognized file content")


def validate_upload(*, data: bytes, filename: str, claimed_type: str, folder: str) -> dict:
    """Return a safe filename, detected MIME, and kind or raise HTTP 415."""
    if not data:
        raise HTTPException(400, "Empty files are not allowed")
    safe_name = Path(filename or "file").name
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension in {"svg", "svgz"} or (claimed_type or "").split(";", 1)[0].lower() == "image/svg+xml":
        raise HTTPException(415, "SVG uploads are not allowed")

    _reject_executable_content(data)
    detected_type = _detect_type(data, extension)
    allowed_extensions = _TYPE_EXTENSIONS[detected_type]
    if extension not in allowed_extensions:
        raise HTTPException(415, "File extension does not match file content")
    if detected_type not in _FOLDER_TYPES.get(folder, set()):
        raise HTTPException(415, "This file type is not allowed for the selected upload category")

    declared = (claimed_type or "").split(";", 1)[0].strip().lower()
    compatible_declared: Iterable[str] = {
        detected_type,
        "application/octet-stream",
        "binary/octet-stream",
        "",
        *_DECLARED_ALIASES.get(detected_type, set()),
    }
    if declared not in compatible_declared:
        raise HTTPException(415, "Declared MIME type does not match file content")
    return {
        "filename": safe_name,
        "content_type": detected_type,
        "kind": "image" if detected_type.startswith("image/") else "file",
    }
