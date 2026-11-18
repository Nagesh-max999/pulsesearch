import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.storage.s3_provider import S3StorageProvider

pytestmark = pytest.mark.asyncio


def _settings(**overrides) -> Settings:
    return Settings(storage_backend="s3", s3_bucket="test-bucket", **overrides)


async def test_save_puts_object_under_user_prefixed_key():
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client) as mock_boto:
        provider = S3StorageProvider(_settings())
        user_id = uuid.uuid4()

        storage_path = await provider.save(user_id, "notes.txt", b"hello world")

        mock_boto.assert_called_once()
        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"].startswith(f"{user_id}/")
        assert call_kwargs["Key"].endswith("_notes.txt")
        assert call_kwargs["Body"] == b"hello world"
        assert storage_path == f"s3://test-bucket/{call_kwargs['Key']}"


async def test_read_gets_object_by_key():
    mock_body = MagicMock()
    mock_body.read.return_value = b"file contents"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_body}

    with patch("boto3.client", return_value=mock_client):
        provider = S3StorageProvider(_settings())
        content = await provider.read("s3://test-bucket/some/key.txt")

    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="some/key.txt")
    assert content == b"file contents"


async def test_read_accepts_a_raw_key_without_the_uri_prefix():
    mock_body = MagicMock()
    mock_body.read.return_value = b"file contents"
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": mock_body}

    with patch("boto3.client", return_value=mock_client):
        provider = S3StorageProvider(_settings())
        await provider.read("some/key.txt")

    mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="some/key.txt")


async def test_delete_removes_object_by_key():
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        provider = S3StorageProvider(_settings())
        await provider.delete("s3://test-bucket/some/key.txt")

    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="some/key.txt")


async def test_client_is_created_once_and_reused():
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client) as mock_boto:
        provider = S3StorageProvider(_settings())
        await provider.delete("some/key.txt")
        await provider.delete("some/other-key.txt")

    mock_boto.assert_called_once()
