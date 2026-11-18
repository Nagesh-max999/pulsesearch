import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import Settings


class UnsupportedFileTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


def safe_filename(original_filename: str) -> str:
    """Strip any path components and non-safe characters, keeping the extension."""
    name = Path(original_filename).name
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem)[:100] or "file"
    return f"{safe_stem}{ext}"


class StorageProvider(ABC):
    """Interface all file storage backends must implement.

    Keeping the rest of the app dependent only on this interface (a storage
    reference string in, bytes out) means the concrete backend — local disk for
    a single-instance deployment, S3/MinIO once storage needs to scale
    independently of the API process — can be swapped via configuration alone,
    the same pattern used for embeddings and reranking.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def validate(self, filename: str, size_bytes: int) -> str:
        """Shared across backends: extension/size limits aren't a storage-medium
        concern, so there's no reason to duplicate this per provider."""
        ext = Path(filename).suffix.lower()
        if ext not in self.settings.allowed_extensions_list:
            raise UnsupportedFileTypeError(ext)
        if size_bytes > self.settings.max_upload_size_bytes:
            raise FileTooLargeError(size_bytes)
        return ext

    @abstractmethod
    async def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        """Persists content, returning an opaque storage reference (local path
        or object key) to pass back to read()/delete() later."""

    @abstractmethod
    async def read(self, storage_path: str) -> bytes:
        """Fetches previously-saved content by its storage reference."""

    @abstractmethod
    async def delete(self, storage_path: str) -> None:
        """Removes previously-saved content. Must be safe to call on content
        that no longer exists (idempotent delete)."""
