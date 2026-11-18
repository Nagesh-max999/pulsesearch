import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.document import DocumentStatus
from app.models.search_event import SearchMode
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.services.embeddings.factory import get_embedding_provider
from app.services.event_bus import DocumentEventBus
from app.services.processing_service import ProcessingService
from app.services.search_service import SearchService

pytestmark = pytest.mark.asyncio

SAMPLE_TEXT = (
    "Improving API performance often starts with database optimization, such as adding "
    "indexes and using connection pooling. Caching frequently accessed data in Redis "
    "reduces load on the primary database. Asynchronous processing and query optimization "
    "further reduce request latency under heavy traffic."
)


async def _create_and_process_document(
    tmp_path,
    db_session: AsyncSession,
    redis_client: Redis,
    user_id: uuid.UUID,
    text: str = SAMPLE_TEXT,
):
    file_path = tmp_path / f"{uuid.uuid4().hex}.txt"
    file_path.write_text(text, encoding="utf-8")

    document_repo = DocumentRepository(db_session)
    document = await document_repo.create(
        user_id=user_id,
        title="perf-notes.txt",
        original_filename="perf-notes.txt",
        storage_path=str(file_path),
        mime_type="text/plain",
        file_size_bytes=len(text.encode()),
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
    return document, document_repo, chunk_repo


async def test_processing_pipeline_completes_and_indexes(
    tmp_path, db_session, redis_client, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    document, document_repo, chunk_repo = await _create_and_process_document(
        tmp_path, db_session, redis_client, user_id
    )

    refreshed = await document_repo.get_by_id(document.id)
    assert refreshed.status == DocumentStatus.COMPLETED
    assert refreshed.raw_text is not None

    chunk_count = await chunk_repo.count_for_document(document.id)
    assert chunk_count >= 1


async def test_processing_pipeline_is_idempotent(
    tmp_path, db_session, redis_client, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    document, document_repo, chunk_repo = await _create_and_process_document(
        tmp_path, db_session, redis_client, user_id
    )
    first_count = await chunk_repo.count_for_document(document.id)

    service = ProcessingService(
        session=db_session,
        document_repo=document_repo,
        chunk_repo=chunk_repo,
        embedding_provider=get_embedding_provider(),
        event_bus=DocumentEventBus(redis_client),
    )
    await service.process(document.id)
    second_count = await chunk_repo.count_for_document(document.id)

    assert first_count == second_count


async def test_keyword_search_finds_exact_term(
    tmp_path, db_session, redis_client, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    await _create_and_process_document(tmp_path, db_session, redis_client, user_id)

    chunk_repo = ChunkRepository(db_session)
    service = SearchService(chunk_repo, get_embedding_provider(), get_settings())

    results, total = await service.search(
        user_id, "connection pooling", SearchMode.KEYWORD, 1, 10
    )
    assert total >= 1
    assert any("pooling" in r["snippet"].lower() for r in results)


async def test_semantic_search_finds_conceptual_match(
    tmp_path, db_session, redis_client, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    await _create_and_process_document(tmp_path, db_session, redis_client, user_id)

    chunk_repo = ChunkRepository(db_session)
    service = SearchService(chunk_repo, get_embedding_provider(), get_settings())

    results, total = await service.search(
        user_id, "how do I make my API faster?", SearchMode.SEMANTIC, 1, 10
    )
    assert total >= 1
    assert results[0]["score"] > 0


async def test_search_is_scoped_to_owning_user(tmp_path, db_session, redis_client, client):
    await client.post(
        "/api/auth/register",
        json={"email": "searcher-a@example.com", "password": "supersecret123"},
    )
    login_a = await client.post(
        "/api/auth/login", json={"email": "searcher-a@example.com", "password": "supersecret123"}
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    me_a = await client.get("/api/auth/me", headers=headers_a)
    user_a_id = uuid.UUID(me_a.json()["id"])
    await _create_and_process_document(tmp_path, db_session, redis_client, user_a_id)

    await client.post(
        "/api/auth/register",
        json={"email": "searcher-b@example.com", "password": "supersecret123"},
    )
    login_b = await client.post(
        "/api/auth/login", json={"email": "searcher-b@example.com", "password": "supersecret123"}
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    me_b = await client.get("/api/auth/me", headers=headers_b)
    user_b_id = uuid.UUID(me_b.json()["id"])

    chunk_repo = ChunkRepository(db_session)
    service = SearchService(chunk_repo, get_embedding_provider(), get_settings())
    results, total = await service.search(
        user_b_id, "connection pooling", SearchMode.KEYWORD, 1, 10
    )

    assert total == 0
    assert results == []
