import asyncio
import uuid

from app.services.storage.base import StorageProvider, safe_filename


class S3StorageProvider(StorageProvider):
    """S3-compatible object storage (AWS S3, MinIO, or anything speaking the S3
    API via s3_endpoint_url) — lets storage scale independently of the API and
    worker processes, and survive an instance being replaced.

    boto3's client is synchronous, so every call is run in a thread rather than
    blocking the event loop — the same tradeoff the local embedding model makes
    for CPU-bound work.
    """

    def __init__(self, settings):
        super().__init__(settings)
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                region_name=self.settings.s3_region,
                endpoint_url=self.settings.s3_endpoint_url or None,
                aws_access_key_id=self.settings.s3_access_key_id or None,
                aws_secret_access_key=self.settings.s3_secret_access_key or None,
            )
        return self._client

    def _key(self, storage_path: str) -> str:
        # Reference returned by save() is "s3://<bucket>/<key>"; accept the raw
        # key too so callers don't have to know the prefix scheme.
        prefix = f"s3://{self.settings.s3_bucket}/"
        return storage_path[len(prefix):] if storage_path.startswith(prefix) else storage_path

    async def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        clean_name = safe_filename(filename)
        key = f"{user_id}/{uuid.uuid4().hex}_{clean_name}"

        def _put():
            self._get_client().put_object(
                Bucket=self.settings.s3_bucket, Key=key, Body=content
            )

        await asyncio.to_thread(_put)
        return f"s3://{self.settings.s3_bucket}/{key}"

    async def read(self, storage_path: str) -> bytes:
        key = self._key(storage_path)

        def _get() -> bytes:
            response = self._get_client().get_object(Bucket=self.settings.s3_bucket, Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(_get)

    async def delete(self, storage_path: str) -> None:
        key = self._key(storage_path)

        def _delete():
            self._get_client().delete_object(Bucket=self.settings.s3_bucket, Key=key)

        await asyncio.to_thread(_delete)
