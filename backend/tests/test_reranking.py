import pytest

from app.core.config import get_settings
from app.services.reranking.base import RerankerError, RerankerProvider
from app.services.search_service import SearchService


class _StubReranker(RerankerProvider):
    def __init__(self, scores: list[float]):
        self.scores = scores
        self.calls: list[tuple[str, list[str]]] = []

    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        self.calls.append((query, candidates))
        return self.scores


class _FailingReranker(RerankerProvider):
    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        raise RerankerError("model unavailable")


def _service(reranker: RerankerProvider) -> SearchService:
    return SearchService(
        chunk_repo=None, embedding_provider=None, settings=get_settings(), reranker=reranker
    )


@pytest.mark.asyncio
async def test_apply_rerank_reorders_results_by_score():
    service = _service(_StubReranker([0.1, 0.9, 0.5]))
    results = [
        {"snippet": "a", "score": 1.0},
        {"snippet": "b", "score": 0.5},
        {"snippet": "c", "score": 0.2},
    ]

    reranked = await service._apply_rerank("query", results)

    assert [r["snippet"] for r in reranked] == ["b", "c", "a"]
    assert reranked[0]["rerank_score"] == 0.9


@pytest.mark.asyncio
async def test_apply_rerank_passes_snippets_as_candidates():
    reranker = _StubReranker([0.5, 0.5])
    service = _service(reranker)
    results = [{"snippet": "first snippet", "score": 1.0}, {"snippet": "second", "score": 0.5}]

    await service._apply_rerank("my query", results)

    assert reranker.calls == [("my query", ["first snippet", "second"])]


@pytest.mark.asyncio
async def test_apply_rerank_falls_back_to_retrieval_order_on_error():
    service = _service(_FailingReranker())
    results = [{"snippet": "a", "score": 1.0}, {"snippet": "b", "score": 0.5}]

    reranked = await service._apply_rerank("query", results)

    assert reranked == results


@pytest.mark.asyncio
async def test_apply_rerank_scores_a_single_result_too():
    # A single candidate still gets scored (not skipped as a trivial no-op):
    # relevance filtering needs to know whether even the only candidate is
    # actually relevant, not just how it compares to others.
    reranker = _StubReranker([0.42])
    service = _service(reranker)
    results = [{"snippet": "only", "score": 1.0}]

    reranked = await service._apply_rerank("query", results)

    assert reranked[0]["rerank_score"] == 0.42
    assert reranker.calls == [("query", ["only"])]


@pytest.mark.asyncio
async def test_apply_rerank_is_noop_for_empty_results():
    reranker = _StubReranker([])
    service = _service(reranker)

    reranked = await service._apply_rerank("query", [])

    assert reranked == []
    assert reranker.calls == []


def test_filter_by_relevance_drops_results_below_threshold():
    service = _service(_StubReranker([]))
    results = [
        {"snippet": "relevant", "rerank_score": 5.7},
        {"snippet": "borderline", "rerank_score": 0.0},
        {"snippet": "irrelevant", "rerank_score": -9.6},
    ]

    filtered = service._filter_by_relevance(results)

    assert [r["snippet"] for r in filtered] == ["relevant", "borderline"]


def test_filter_by_relevance_keeps_unscored_results():
    # rerank_score is None when reranking was skipped or failed (see
    # _apply_rerank's except branch) — nothing to filter on, so keep as-is
    # rather than discarding results that were never judged.
    service = _service(_StubReranker([]))
    results = [{"snippet": "unscored", "rerank_score": None}]

    filtered = service._filter_by_relevance(results)

    assert filtered == results


def test_filter_by_relevance_respects_configured_threshold(monkeypatch):
    monkeypatch.setenv("RERANK_MIN_SCORE", "-5")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        service = SearchService(
            chunk_repo=None,
            embedding_provider=None,
            settings=get_settings(),
            reranker=_StubReranker([]),
        )
        results = [{"snippet": "a", "rerank_score": -9.6}, {"snippet": "b", "rerank_score": -2.0}]

        filtered = service._filter_by_relevance(results)

        assert [r["snippet"] for r in filtered] == ["b"]
    finally:
        get_settings.cache_clear()
