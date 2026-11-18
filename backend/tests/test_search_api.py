import uuid

import pytest

from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.services.embeddings.factory import get_embedding_provider
from app.services.event_bus import DocumentEventBus
from app.services.processing_service import ProcessingService

pytestmark = pytest.mark.asyncio

SAMPLE_TEXT = (
    "Improving API performance often starts with database optimization, such as adding "
    "indexes and using connection pooling. Caching frequently accessed data in Redis "
    "reduces load on the primary database."
)


async def _index_sample_document(tmp_path, db_session, redis_client, user_id):
    file_path = tmp_path / f"{uuid.uuid4().hex}.txt"
    file_path.write_text(SAMPLE_TEXT, encoding="utf-8")

    document_repo = DocumentRepository(db_session)
    document = await document_repo.create(
        user_id=user_id,
        title="perf-notes.txt",
        original_filename="perf-notes.txt",
        storage_path=str(file_path),
        mime_type="text/plain",
        file_size_bytes=len(SAMPLE_TEXT.encode()),
    )
    await db_session.commit()

    chunk_repo = ChunkRepository(db_session)
    service = ProcessingService(
        session=db_session,
        document_repo=document_repo,
        chunk_repo=chunk_repo,
        embedding_provider=get_embedding_provider(),
        event_bus=DocumentEventBus(redis_client),
    )
    await service.process(document.id)


async def test_search_requires_auth(client):
    resp = await client.get("/api/search", params={"q": "caching"})
    assert resp.status_code == 401


async def test_search_endpoint_returns_results_and_records_event(
    tmp_path, db_session, redis_client, client, auth_headers, registered_user
):
    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    await _index_sample_document(tmp_path, db_session, redis_client, user_id)

    resp = await client.get(
        "/api/search", params={"q": "connection pooling", "mode": "KEYWORD"}, headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["mode"] == "KEYWORD"
    assert body["latency_ms"] >= 0

    analytics = await client.get("/api/analytics/search", headers=auth_headers)
    assert analytics.status_code == 200
    assert analytics.json()["total_searches"] >= 1
    assert analytics.json()["keyword_searches"] >= 1


async def test_search_zero_results_tracked_in_analytics(client, auth_headers):
    resp = await client.get(
        "/api/search", params={"q": "nonexistent-term-xyz", "mode": "KEYWORD"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    analytics = await client.get("/api/analytics/search", headers=auth_headers)
    assert analytics.json()["zero_result_searches"] >= 1


async def test_search_result_is_cached(tmp_path, db_session, redis_client, client, auth_headers):
    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    await _index_sample_document(tmp_path, db_session, redis_client, user_id)

    first = await client.get(
        "/api/search", params={"q": "caching", "mode": "KEYWORD"}, headers=auth_headers
    )
    cache_key_prefix = f"search:{user_id}:KEYWORD:1:10:"
    keys = [k async for k in redis_client.scan_iter(match=f"{cache_key_prefix}*")]
    assert len(keys) == 1
    assert first.status_code == 200


async def test_document_analytics_counts_by_status(
    tmp_path, db_session, redis_client, client, auth_headers
):
    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])
    await _index_sample_document(tmp_path, db_session, redis_client, user_id)

    resp = await client.get("/api/analytics/documents", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["by_status"]["COMPLETED"] == 1
