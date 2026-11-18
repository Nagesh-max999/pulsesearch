from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageProvider
from app.services.storage.local_provider import LocalStorageProvider
from app.services.storage.s3_provider import S3StorageProvider


@lru_cache
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3StorageProvider(settings)
    return LocalStorageProvider(settings)
