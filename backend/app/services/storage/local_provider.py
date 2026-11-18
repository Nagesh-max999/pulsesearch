import uuid
from pathlib import Path

from app.services.storage.base import StorageProvider, safe_filename


class LocalStorageProvider(StorageProvider):
    """Local-disk file storage — the default, zero-config backend.

    Simplest option for a single-instance deployment; doesn't let storage scale
    independently of the API/worker processes, which is what S3StorageProvider
    is for.
    """

    def __init__(self, settings):
        super().__init__(settings)
        self.base_dir = Path(self.settings.upload_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        clean_name = safe_filename(filename)
        unique_name = f"{uuid.uuid4().hex}_{clean_name}"
        user_dir = self.base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        target_path = (user_dir / unique_name).resolve()
        if self.base_dir.resolve() not in target_path.parents:
            raise ValueError("Resolved path escapes upload directory")

        target_path.write_bytes(content)
        return str(target_path)

    async def read(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()

    async def delete(self, storage_path: str) -> None:
        path = Path(storage_path)
        if path.exists() and self.base_dir.resolve() in path.resolve().parents:
            path.unlink()
