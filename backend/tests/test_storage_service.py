import uuid
from pathlib import Path

import pytest

from app.services.storage.base import FileTooLargeError, UnsupportedFileTypeError, safe_filename
from app.services.storage.factory import get_storage_provider
from app.services.storage.local_provider import LocalStorageProvider


def test_safe_filename_strips_path_traversal():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("..\\..\\windows\\system32\\config") == "config"


def test_safe_filename_sanitizes_special_characters():
    result = safe_filename("my file (final) v2!.txt")
    assert result.endswith(".txt")
    assert " " not in result
    assert "(" not in result


def test_storage_validate_rejects_disallowed_extension(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    with pytest.raises(UnsupportedFileTypeError):
        service.validate("virus.exe", 100)
    get_settings.cache_clear()


def test_storage_validate_rejects_oversized_file(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    with pytest.raises(FileTooLargeError):
        service.validate("big.txt", 2 * 1024 * 1024)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_save_writes_within_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    user_id = uuid.uuid4()

    path = await service.save(user_id, "notes.txt", b"hello world")
    saved_path = Path(path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"hello world"
    assert tmp_path.resolve() in saved_path.resolve().parents
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_read_returns_saved_content(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    user_id = uuid.uuid4()

    path = await service.save(user_id, "notes.txt", b"hello again")
    content = await service.read(path)
    assert content == b"hello again"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_delete_removes_saved_content(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    user_id = uuid.uuid4()

    path = await service.save(user_id, "notes.txt", b"to be deleted")
    await service.delete(path)
    assert not Path(path).exists()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_delete_is_idempotent_for_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    service = LocalStorageProvider(get_settings())
    await service.delete(str(tmp_path / "never-existed.txt"))  # must not raise
    get_settings.cache_clear()


def test_factory_returns_local_provider_by_default(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    get_settings.cache_clear()
    get_storage_provider.cache_clear()
    provider = get_storage_provider()
    assert isinstance(provider, LocalStorageProvider)
    get_settings.cache_clear()
    get_storage_provider.cache_clear()


def test_factory_returns_s3_provider_when_configured(monkeypatch):
    from app.core.config import get_settings
    from app.services.storage.s3_provider import S3StorageProvider

    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    get_settings.cache_clear()
    get_storage_provider.cache_clear()
    try:
        provider = get_storage_provider()
        assert isinstance(provider, S3StorageProvider)
    finally:
        monkeypatch.delenv("STORAGE_BACKEND", raising=False)
        get_settings.cache_clear()
        get_storage_provider.cache_clear()
