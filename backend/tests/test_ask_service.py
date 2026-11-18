import uuid

import pytest

from app.core.config import get_settings
from app.models.search_event import SearchMode
from app.services.ai_answers.base import AIAnswerProvider
from app.services.ask_service import NO_CONTEXT_ANSWER, AskService


class _StubSearchService:
    def __init__(self, results: list[dict]):
        self.results = results
        self.calls: list[tuple] = []

    async def search(self, user_id, query, mode, page, page_size):
        self.calls.append((user_id, query, mode, page, page_size))
        return self.results, len(self.results)


class _StubAnswerProvider(AIAnswerProvider):
    def __init__(self, text: str = "stub answer"):
        self.text = text
        self.calls: list[tuple] = []

    async def answer(self, question: str, context_chunks: list[dict]) -> str:
        self.calls.append((question, context_chunks))
        return self.text


def _result(document_id=None, title="doc.txt", snippet="some snippet"):
    return {
        "document_id": document_id or uuid.uuid4(),
        "title": title,
        "snippet": snippet,
        "score": 1.0,
    }


@pytest.mark.asyncio
async def test_ask_returns_no_context_answer_without_calling_the_model():
    search_service = _StubSearchService(results=[])
    answer_provider = _StubAnswerProvider()
    service = AskService(search_service, answer_provider, get_settings())

    result = await service.ask(uuid.uuid4(), "anything")

    assert result["answer"] == NO_CONTEXT_ANSWER
    assert result["citations"] == []
    assert answer_provider.calls == []  # never pays for a call with no grounding


@pytest.mark.asyncio
async def test_ask_passes_search_results_as_context_and_citations():
    doc_id = uuid.uuid4()
    search_service = _StubSearchService(
        results=[_result(document_id=doc_id, title="notes.txt", snippet="relevant text")]
    )
    answer_provider = _StubAnswerProvider(text="The answer, per your notes.")
    service = AskService(search_service, answer_provider, get_settings())

    result = await service.ask(uuid.uuid4(), "what does it say?")

    assert result["answer"] == "The answer, per your notes."
    assert result["citations"] == [
        {"document_id": doc_id, "title": "notes.txt", "snippet": "relevant text"}
    ]
    question, context = answer_provider.calls[0]
    assert question == "what does it say?"
    assert context == [{"title": "notes.txt", "content": "relevant text"}]


@pytest.mark.asyncio
async def test_ask_searches_in_hybrid_mode_with_configured_context_size():
    search_service = _StubSearchService(results=[_result()])
    settings = get_settings()
    service = AskService(search_service, _StubAnswerProvider(), settings)
    user_id = uuid.uuid4()

    await service.ask(user_id, "question")

    called_user_id, query, mode, page, page_size = search_service.calls[0]
    assert called_user_id == user_id
    assert query == "question"
    assert mode == SearchMode.HYBRID
    assert page == 1
    assert page_size == settings.ai_answers_context_chunks


@pytest.mark.asyncio
async def test_ask_includes_multiple_citations_in_result_order():
    results = [_result(title="a.txt"), _result(title="b.txt"), _result(title="c.txt")]
    search_service = _StubSearchService(results=results)
    service = AskService(search_service, _StubAnswerProvider(), get_settings())

    result = await service.ask(uuid.uuid4(), "question")

    assert [c["title"] for c in result["citations"]] == ["a.txt", "b.txt", "c.txt"]
