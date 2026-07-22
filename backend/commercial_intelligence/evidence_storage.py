"""Private local and durable S3-compatible evidence/export storage providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import base64
from dataclasses import dataclass
import hashlib
from pathlib import Path
import os
import re
import secrets
from typing import Any

from operations.errors import StorageOperationError


_LOCAL_KEY_PATTERN = re.compile(r"^[a-f0-9]{2}/[a-f0-9]{48}\.[a-z0-9]{1,8}$")
_OBJECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,500}$")
_CONTENT_TYPES = {
    "pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
    "jpeg": "image/jpeg", "json": "application/json",
}


@dataclass(frozen=True)
class StorageObjectMetadata:
    size_bytes: int
    content_type: str | None
    checksum_sha256: str | None
    soft_deleted: bool = False


class EvidenceStorage(ABC):
    provider_name = "unknown"
    durable = False

    @abstractmethod
    async def save(
        self, data: bytes, extension: str, *, content_type: str | None = None,
        checksum_sha256: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    async def exists(self, storage_key: str) -> bool: ...

    @abstractmethod
    async def metadata(self, storage_key: str) -> StorageObjectMetadata: ...

    @abstractmethod
    async def mark_deleted(self, storage_key: str) -> None: ...

    @abstractmethod
    async def physical_delete(self, storage_key: str) -> None: ...

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    def generate_safe_download_reference(self, evidence_id: str) -> str:
        return f"/api/campaign-evidence/{evidence_id}/download"

    async def generate_temporary_download_reference(self, storage_key: str, ttl_seconds: int) -> str:
        del storage_key, ttl_seconds
        raise StorageOperationError("signed_reference_unavailable")


class LocalPrivateEvidenceStorage(EvidenceStorage):
    provider_name = "local"
    durable = False

    def __init__(self, root: str | Path | None = None):
        configured = Path(root or os.environ.get("EVIDENCE_STORAGE_ROOT", "./private_evidence"))
        self.root = configured.resolve()
        public_root = Path(os.environ.get("UPLOAD_ROOT", "./uploads")).resolve()
        if self.root == public_root or public_root in self.root.parents:
            raise RuntimeError("Evidence storage must be outside the public upload directory")
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(
        self, data: bytes, extension: str, *, content_type: str | None = None,
        checksum_sha256: str | None = None,
    ) -> str:
        del content_type, checksum_sha256
        maximum = _bounded_int("EVIDENCE_MAX_UPLOAD_MB", 8, 1, 25) * 1024 * 1024
        if not data or len(data) > maximum:
            raise StorageOperationError("invalid_object_size")
        token = secrets.token_hex(24)
        key = f"{token[:2]}/{token}.{extension.casefold()}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("xb") as output:
                output.write(data)
        except FileExistsError:
            raise
        except OSError as exc:
            raise StorageOperationError("local_write_failed") from exc
        return key

    async def read(self, storage_key: str) -> bytes:
        try:
            return self._path(storage_key).read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise StorageOperationError("local_read_failed") from exc

    async def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()

    async def metadata(self, storage_key: str) -> StorageObjectMetadata:
        path = self._path(storage_key)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise StorageOperationError("local_metadata_failed") from exc
        extension = path.suffix.lstrip(".").casefold()
        return StorageObjectMetadata(
            size_bytes=len(data), content_type=_CONTENT_TYPES.get(extension),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
        )

    async def mark_deleted(self, storage_key: str) -> None:
        # Logical deletion remains in Mongo; bytes stay private until approved maintenance.
        self._path(storage_key)

    async def physical_delete(self, storage_key: str) -> None:
        try:
            self._path(storage_key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageOperationError("local_delete_failed") from exc

    def _path(self, storage_key: str) -> Path:
        if not _LOCAL_KEY_PATTERN.fullmatch(storage_key):
            raise ValueError("Invalid private storage key")
        resolved = (self.root / storage_key).resolve()
        if self.root not in resolved.parents:
            raise ValueError("Invalid private storage path")
        return resolved


class S3CompatibleEvidenceStorage(EvidenceStorage):
    """Private S3-compatible storage with bounded SDK retries and timeouts."""

    provider_name = "s3"
    durable = True

    def __init__(self, *, client: Any | None = None):
        self.bucket = _required("EVIDENCE_STORAGE_BUCKET")
        self.region = _required("EVIDENCE_STORAGE_REGION")
        self.prefix = _safe_prefix(os.environ.get("EVIDENCE_STORAGE_PREFIX", "brandkrt-private"))
        self.signed_url_ttl = _bounded_int("EVIDENCE_STORAGE_SIGNED_URL_TTL_SECONDS", 300, 30, 3600)
        self.operation_timeout = _bounded_float("EVIDENCE_STORAGE_OPERATION_TIMEOUT_SECONDS", 12.0, 1.0, 60.0)
        self.max_bytes = _bounded_int("EVIDENCE_MAX_UPLOAD_MB", 8, 1, 25) * 1024 * 1024
        self.encryption_mode = os.environ.get("EVIDENCE_STORAGE_ENCRYPTION_MODE", "AES256").strip() or "AES256"
        self.kms_key_id = os.environ.get("EVIDENCE_STORAGE_KMS_KEY_ID", "").strip()
        self._client = client or self._build_client()

    def _build_client(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise StorageOperationError("s3_sdk_unavailable") from exc
        return boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=os.environ.get("EVIDENCE_STORAGE_ENDPOINT") or None,
            aws_access_key_id=_required("EVIDENCE_STORAGE_ACCESS_KEY"),
            aws_secret_access_key=_required("EVIDENCE_STORAGE_SECRET_KEY"),
            config=Config(
                connect_timeout=_bounded_float("EVIDENCE_STORAGE_CONNECT_TIMEOUT_SECONDS", 4.0, 1.0, 30.0),
                read_timeout=_bounded_float("EVIDENCE_STORAGE_READ_TIMEOUT_SECONDS", 10.0, 1.0, 60.0),
                retries={"mode": "standard", "total_max_attempts": _bounded_int("EVIDENCE_STORAGE_MAX_ATTEMPTS", 3, 1, 5)},
                signature_version="s3v4",
            ),
        )

    async def save(
        self, data: bytes, extension: str, *, content_type: str | None = None,
        checksum_sha256: str | None = None,
    ) -> str:
        if not data or len(data) > self.max_bytes:
            raise StorageOperationError("invalid_object_size")
        checksum = checksum_sha256 or hashlib.sha256(data).hexdigest()
        if checksum != hashlib.sha256(data).hexdigest():
            raise StorageOperationError("checksum_mismatch")
        token = secrets.token_hex(24)
        key = f"{self.prefix}/{token[:2]}/{token}.{extension.casefold()}"
        kwargs = {
            "Bucket": self.bucket, "Key": key, "Body": data, "ContentLength": len(data),
            "ContentType": content_type or _CONTENT_TYPES.get(extension.casefold(), "application/octet-stream"),
            "ChecksumSHA256": base64.b64encode(bytes.fromhex(checksum)).decode("ascii"),
            "Metadata": {"sha256": checksum, "state": "active"},
            "ServerSideEncryption": self.encryption_mode, "IfNoneMatch": "*",
        }
        if self.encryption_mode == "aws:kms":
            kwargs["SSEKMSKeyId"] = self.kms_key_id
        try:
            await self._call(self._client.put_object, **kwargs)
        except StorageOperationError:
            raise
        return key

    async def read(self, storage_key: str) -> bytes:
        key = self._key(storage_key)
        response = await self._call(self._client.get_object, Bucket=self.bucket, Key=key)
        body = response.get("Body")
        try:
            data = await asyncio.wait_for(asyncio.to_thread(body.read), timeout=self.operation_timeout)
        except Exception as exc:
            raise StorageOperationError("s3_read_failed") from exc
        expected = str((response.get("Metadata") or {}).get("sha256") or "")
        if expected and hashlib.sha256(data).hexdigest() != expected:
            raise StorageOperationError("checksum_mismatch")
        return data

    async def exists(self, storage_key: str) -> bool:
        try:
            await self._head(storage_key)
            return True
        except FileNotFoundError:
            return False

    async def metadata(self, storage_key: str) -> StorageObjectMetadata:
        response = await self._head(storage_key)
        metadata = response.get("Metadata") or {}
        tags = await self._call(
            self._client.get_object_tagging, Bucket=self.bucket, Key=self._key(storage_key),
        )
        tag_values = {item.get("Key"): item.get("Value") for item in tags.get("TagSet", [])}
        return StorageObjectMetadata(
            size_bytes=max(0, int(response.get("ContentLength", 0))),
            content_type=response.get("ContentType"), checksum_sha256=metadata.get("sha256"),
            soft_deleted=tag_values.get("brandkrt-state") == "soft-deleted",
        )

    async def mark_deleted(self, storage_key: str) -> None:
        key = self._key(storage_key)
        await self._call(
            self._client.put_object_tagging, Bucket=self.bucket, Key=key,
            Tagging={"TagSet": [{"Key": "brandkrt-state", "Value": "soft-deleted"}]},
        )

    async def physical_delete(self, storage_key: str) -> None:
        await self._call(self._client.delete_object, Bucket=self.bucket, Key=self._key(storage_key))

    async def generate_temporary_download_reference(self, storage_key: str, ttl_seconds: int) -> str:
        ttl = min(self.signed_url_ttl, max(30, int(ttl_seconds)))
        try:
            return await asyncio.wait_for(asyncio.to_thread(
                self._client.generate_presigned_url, "get_object",
                Params={"Bucket": self.bucket, "Key": self._key(storage_key)}, ExpiresIn=ttl,
            ), timeout=self.operation_timeout)
        except Exception as exc:
            raise StorageOperationError("signed_reference_failed") from exc

    async def health_check(self) -> bool:
        await self._call(self._client.head_bucket, Bucket=self.bucket)
        return True

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            await asyncio.to_thread(close)

    async def _head(self, storage_key: str) -> dict:
        try:
            return await self._call(
                self._client.head_object, Bucket=self.bucket, Key=self._key(storage_key),
            )
        except StorageOperationError as exc:
            if exc.code == "object_missing":
                raise FileNotFoundError(storage_key) from None
            raise

    async def _call(self, function, **kwargs):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(function, **kwargs), timeout=self.operation_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise StorageOperationError("storage_timeout") from exc
        except Exception as exc:
            status = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if status == 404 or code in {"NoSuchKey", "NotFound", "404"}:
                raise StorageOperationError("object_missing") from exc
            if status == 412 or code in {"PreconditionFailed", "ConditionalRequestConflict"}:
                raise StorageOperationError("duplicate_object_key") from exc
            raise StorageOperationError("storage_unavailable") from exc

    def _key(self, storage_key: str) -> str:
        if not _OBJECT_KEY_PATTERN.fullmatch(storage_key) or ".." in storage_key.split("/"):
            raise ValueError("Invalid private storage key")
        if not storage_key.startswith(f"{self.prefix}/"):
            raise ValueError("Invalid private storage prefix")
        return storage_key


class InMemoryEvidenceStorage(EvidenceStorage):
    provider_name = "memory"
    durable = False

    def __init__(self):
        self.items: dict[str, bytes] = {}
        self.object_metadata: dict[str, StorageObjectMetadata] = {}
        self.deleted: set[str] = set()

    async def save(
        self, data: bytes, extension: str, *, content_type: str | None = None,
        checksum_sha256: str | None = None,
    ) -> str:
        token = secrets.token_hex(24)
        key = f"{token[:2]}/{token}.{extension.casefold()}"
        if key in self.items:
            raise FileExistsError(key)
        self.items[key] = bytes(data)
        self.object_metadata[key] = StorageObjectMetadata(
            size_bytes=len(data), content_type=content_type or _CONTENT_TYPES.get(extension.casefold()),
            checksum_sha256=checksum_sha256 or hashlib.sha256(data).hexdigest(),
        )
        return key

    async def read(self, storage_key: str) -> bytes:
        if storage_key not in self.items:
            raise FileNotFoundError(storage_key)
        return self.items[storage_key]

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.items

    async def metadata(self, storage_key: str) -> StorageObjectMetadata:
        if storage_key not in self.object_metadata:
            raise FileNotFoundError(storage_key)
        metadata = self.object_metadata[storage_key]
        return StorageObjectMetadata(
            size_bytes=metadata.size_bytes, content_type=metadata.content_type,
            checksum_sha256=metadata.checksum_sha256, soft_deleted=storage_key in self.deleted,
        )

    async def mark_deleted(self, storage_key: str) -> None:
        if storage_key in self.items:
            self.deleted.add(storage_key)

    async def physical_delete(self, storage_key: str) -> None:
        self.items.pop(storage_key, None)
        self.object_metadata.pop(storage_key, None)
        self.deleted.discard(storage_key)


def build_evidence_storage_from_env() -> EvidenceStorage:
    provider = os.environ.get("EVIDENCE_STORAGE_PROVIDER", "local").strip().casefold() or "local"
    if provider == "local":
        return LocalPrivateEvidenceStorage()
    if provider == "s3":
        return S3CompatibleEvidenceStorage()
    raise StorageOperationError("unsupported_storage_provider")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StorageOperationError("storage_configuration_error")
    return value


def _safe_prefix(value: str) -> str:
    prefix = value.strip().strip("/")
    if not prefix or not _OBJECT_KEY_PATTERN.fullmatch(prefix) or ".." in prefix.split("/"):
        raise StorageOperationError("storage_configuration_error")
    return prefix


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise StorageOperationError("storage_configuration_error") from exc
    if not minimum <= value <= maximum:
        raise StorageOperationError("storage_configuration_error")
    return value


def _bounded_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise StorageOperationError("storage_configuration_error") from exc
    if not minimum <= value <= maximum:
        raise StorageOperationError("storage_configuration_error")
    return value
