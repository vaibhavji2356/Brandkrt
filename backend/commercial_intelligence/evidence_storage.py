"""Private evidence/export storage without permanent public URLs."""

from abc import ABC, abstractmethod
from pathlib import Path
import os
import re
import secrets


_KEY_PATTERN = re.compile(r"^[a-f0-9]{2}/[a-f0-9]{48}\.[a-z0-9]{1,8}$")


class EvidenceStorage(ABC):
    @abstractmethod
    async def save(self, data: bytes, extension: str) -> str: ...

    @abstractmethod
    async def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    async def exists(self, storage_key: str) -> bool: ...

    @abstractmethod
    async def mark_deleted(self, storage_key: str) -> None: ...

    def generate_safe_download_reference(self, evidence_id: str) -> str:
        return f"/api/campaign-evidence/{evidence_id}/download"


class LocalPrivateEvidenceStorage(EvidenceStorage):
    def __init__(self, root: str | Path | None = None):
        configured = Path(root or os.environ.get("EVIDENCE_STORAGE_ROOT", "./private_evidence"))
        self.root = configured.resolve()
        public_root = Path(os.environ.get("UPLOAD_ROOT", "./uploads")).resolve()
        if self.root == public_root or public_root in self.root.parents:
            raise RuntimeError("Evidence storage must be outside the public upload directory")
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, data: bytes, extension: str) -> str:
        token = secrets.token_hex(24)
        key = f"{token[:2]}/{token}.{extension.casefold()}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
        return key

    async def read(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()

    async def exists(self, storage_key: str) -> bool:
        return self._path(storage_key).is_file()

    async def mark_deleted(self, storage_key: str) -> None:
        # Soft deletion deliberately retains bytes until an explicit retention operation.
        self._path(storage_key)

    def _path(self, storage_key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(storage_key):
            raise ValueError("Invalid private storage key")
        resolved = (self.root / storage_key).resolve()
        if self.root not in resolved.parents:
            raise ValueError("Invalid private storage path")
        return resolved


class InMemoryEvidenceStorage(EvidenceStorage):
    def __init__(self):
        self.items: dict[str, bytes] = {}
        self.deleted: set[str] = set()

    async def save(self, data: bytes, extension: str) -> str:
        token = secrets.token_hex(24)
        key = f"{token[:2]}/{token}.{extension.casefold()}"
        self.items[key] = bytes(data)
        return key

    async def read(self, storage_key: str) -> bytes:
        if storage_key not in self.items:
            raise FileNotFoundError(storage_key)
        return self.items[storage_key]

    async def exists(self, storage_key: str) -> bool:
        return storage_key in self.items

    async def mark_deleted(self, storage_key: str) -> None:
        if storage_key in self.items:
            self.deleted.add(storage_key)
