import uuid

import pytest

from app.api.routes.ask import get_ai_answer_provider_optional
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.services.ai_answers.base import AIAnswerProvider
from app.services.embeddings.factory import get_embedding_provider
from app.services.event_bus import DocumentEventBus
from app.services.processing_service import ProcessingService

pytestmark = pytest.mark.asyncio

SAMPLE_TEXT = (
    "Improving API performance often starts with database optimization, such as adding "
    "indexes and using connection pooling. Caching frequently accessed data in Redis "
    "reduces load on the primary database."
)


class _StubAnswerProvider(AIAnswerProvider):
    def __init__(self, text: str = "Add indexes and use connection pooling."):
        self.text = text
        self.calls: list[tuple] = []

    async def answer(self, question: str, context_chunks: list[dict]) -> str:
        self.calls.append((question, context_chunks))
        return self.text


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


async def test_ask_requires_auth(client):
    resp = await client.get("/api/ask", params={"q": "how do I speed up my API?"})
    assert resp.status_code == 401


async def test_ask_returns_503_when_disabled(client, auth_headers):
    # AI_ANSWERS_ENABLED=false by default in the test environment (conftest.py).
    resp = await client.get(
        "/api/ask", params={"q": "how do I speed up my API?"}, headers=auth_headers
    )
    assert resp.status_code == 503


async def test_ask_returns_503_when_enabled_without_api_key(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AI_ANSWERS_ENABLED", "true")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    try:
        resp = await client.get(
            "/api/ask", params={"q": "how do I speed up my API?"}, headers=auth_headers
        )
        assert resp.status_code == 503
    finally:
        get_settings.cache_clear()


async def test_ask_with_no_matching_documents_skips_the_model(app, client, auth_headers):
    stub = _StubAnswerProvider()
    app.dependency_overrides[get_ai_answer_provider_optional] = lambda: stub

    resp = await client.get(
        "/api/ask", params={"q": "something not in any document"}, headers=auth_headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == []
    assert "couldn't find" in body["answer"].lower()
    assert stub.calls == []  # never pays for a call with nothing to ground it


async def test_ask_end_to_end_with_real_retrieval_and_stub_model(
    app, tmp_path, db_session, redis_client, client, auth_headers, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    await _index_sample_document(tmp_path, db_session, redis_client, user_id)

    stub = _StubAnswerProvider(text="Add indexes and use connection pooling.")
    app.dependency_overrides[get_ai_answer_provider_optional] = lambda: stub

    resp = await client.get(
        "/api/ask", params={"q": "how do I improve API performance?"}, headers=auth_headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Add indexes and use connection pooling."
    assert body["question"] == "how do I improve API performance?"
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["title"] == "perf-notes.txt"
    assert body["latency_ms"] >= 0

    # The model was actually called with real, retrieved context — not a
    # placeholder — proving the route wires search -> AskService -> provider.
    assert len(stub.calls) == 1
    question, context_chunks = stub.calls[0]
    assert question == "how do I improve API performance?"
    assert any("connection pooling" in c["content"] for c in context_chunks)


async def test_ask_response_is_cached(
    app, tmp_path, db_session, redis_client, client, auth_headers, registered_user
):
    user_id = uuid.UUID(registered_user["id"])
    await _index_sample_document(tmp_path, db_session, redis_client, user_id)

    stub = _StubAnswerProvider()
    app.dependency_overrides[get_ai_answer_provider_optional] = lambda: stub

    params = {"q": "how do I improve API performance?"}
    first = await client.get("/api/ask", params=params, headers=auth_headers)
    assert first.status_code == 200
    assert len(stub.calls) == 1

    second = await client.get("/api/ask", params=params, headers=auth_headers)
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(stub.calls) == 1  # served from cache, model not called again


async def test_ask_endpoint_returns_429_once_rate_limited(
    app, client, auth_headers, monkeypatch
):
    from app.core.config import get_settings

    stub = _StubAnswerProvider()
    app.dependency_overrides[get_ai_answer_provider_optional] = lambda: stub

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_ASK_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        first = await client.get(
            "/api/ask", params={"q": "unique first question"}, headers=auth_headers
        )
        assert first.status_code == 200

        limited = await client.get(
            "/api/ask", params={"q": "a different unique question"}, headers=auth_headers
        )
        assert limited.status_code == 429
    finally:
        get_settings.cache_clear()
