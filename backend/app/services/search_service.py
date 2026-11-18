import logging
import re
import uuid

from app.core.config import Settings
from app.core.metrics import SEARCH_REQUESTS
from app.models.search_event import SearchMode
from app.repositories.chunk_repo import ChunkRepository
from app.services.embeddings.base import EmbeddingProvider
from app.services.reranking.base import RerankerError, RerankerProvider

logger = logging.getLogger(__name__)


class SearchService:
    """Executes keyword, semantic, and hybrid search.

    Hybrid combines Postgres full-text rank (ts_rank_cd, unbounded) and cosine
    similarity (0..1) with configurable weights:

        final_score = keyword_weight * normalized_keyword_score
                    + semantic_weight * semantic_score

    Keyword scores are min-max normalized per result page before blending since
    ts_rank_cd has no fixed upper bound, while cosine similarity is already in
    [0, 1]. The 0.6/0.4 default favors precise term matches over broader semantic
    matches, which suits short technical queries; document search corpora with more
    conceptual/paraphrased queries may prefer the reverse. This is a reasonable
    starting point, not a proven-optimal formula — it should be tuned against real
    query logs (see search_events).
    """

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        embedding_provider: EmbeddingProvider,
        settings: Settings,
        reranker: RerankerProvider | None = None,
    ):
        self.chunk_repo = chunk_repo
        self.embedding_provider = embedding_provider
        self.settings = settings
        self.reranker = reranker

    async def search(
        self, user_id: uuid.UUID, query: str, mode: SearchMode, page: int, page_size: int
    ) -> tuple[list[dict], int]:
        SEARCH_REQUESTS.labels(mode=mode.value).inc()
        offset = (page - 1) * page_size
        use_rerank = self.reranker is not None and self.settings.rerank_enabled

        if not use_rerank:
            if mode == SearchMode.KEYWORD:
                rows, total = await self.chunk_repo.keyword_search(
                    user_id, query, page_size, offset
                )
                return self._to_results(rows, query, keyword=True, semantic=False), total

            if mode == SearchMode.SEMANTIC:
                embedding = await self.embedding_provider.embed_query(query)
                rows, total = await self.chunk_repo.semantic_search(
                    user_id, embedding, page_size, offset
                )
                return self._to_results(rows, query, keyword=False, semantic=True), total

            return await self._hybrid_search(user_id, query, page_size, offset)

        # Reranking path: retrieve a larger candidate pool at offset 0 (so the
        # cross-encoder sees more than one page's worth of candidates to choose
        # from), rerank the pool, then paginate over the reranked order.
        pool_size = max(offset + page_size, self.settings.rerank_candidate_pool)

        if mode == SearchMode.KEYWORD:
            rows, total = await self.chunk_repo.keyword_search(user_id, query, pool_size, 0)
            results = self._to_results(rows, query, keyword=True, semantic=False)
        elif mode == SearchMode.SEMANTIC:
            embedding = await self.embedding_provider.embed_query(query)
            rows, total = await self.chunk_repo.semantic_search(user_id, embedding, pool_size, 0)
            results = self._to_results(rows, query, keyword=False, semantic=True)
        else:
            results, total = await self._hybrid_search(user_id, query, pool_size, 0)

        results = await self._apply_rerank(query, results)
        results = self._filter_by_relevance(results)
        total = len(results)
        return results[offset : offset + page_size], total

    def _filter_by_relevance(self, results: list[dict]) -> list[dict]:
        """Drops results the reranker judged not actually relevant.

        The reranker's judgment is a more reliable relevance signal than "was
        it in the top-K retrieved" — see rerank_min_score's docstring. Only
        filters results that were actually scored: a reranker failure leaves
        rerank_score unset (see _apply_rerank's except branch), and falling
        back to unfiltered retrieval order there is preferable to discarding
        every result because none could be judged.
        """
        return [
            r
            for r in results
            if r["rerank_score"] is None or r["rerank_score"] >= self.settings.rerank_min_score
        ]

    async def _apply_rerank(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results
        try:
            scores = await self.reranker.rerank(query, [r["snippet"] for r in results])
        except RerankerError as exc:
            logger.warning("Reranker unavailable, falling back to retrieval order: %s", exc)
            return results

        for result, score in zip(results, scores, strict=True):
            result["rerank_score"] = round(score, 6)
        return sorted(results, key=lambda r: r["rerank_score"], reverse=True)

    async def _hybrid_search(
        self, user_id: uuid.UUID, query: str, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        embedding = await self.embedding_provider.embed_query(query)

        keyword_rows, keyword_total = await self.chunk_repo.keyword_search(
            user_id, query, limit * 3, 0
        )
        semantic_rows, semantic_total = await self.chunk_repo.semantic_search(
            user_id, embedding, limit * 3, 0
        )

        max_keyword = max((r["score"] for r in keyword_rows), default=0.0) or 1.0
        merged: dict[uuid.UUID, dict] = {}

        for row in keyword_rows:
            norm_score = row["score"] / max_keyword
            merged[row["document_id"]] = {
                **row,
                "keyword_score": norm_score,
                "semantic_score": 0.0,
            }

        for row in semantic_rows:
            existing = merged.get(row["document_id"])
            if existing is None:
                merged[row["document_id"]] = {
                    **row,
                    "keyword_score": 0.0,
                    "semantic_score": row["score"],
                }
            else:
                existing["semantic_score"] = max(existing["semantic_score"], row["score"])

        for entry in merged.values():
            entry["score"] = (
                self.settings.hybrid_keyword_weight * entry["keyword_score"]
                + self.settings.hybrid_semantic_weight * entry["semantic_score"]
            )

        ranked = sorted(merged.values(), key=lambda r: r["score"], reverse=True)
        total = len(ranked)
        page_rows = ranked[offset : offset + limit]
        return self._to_results(page_rows, query, keyword=True, semantic=True), total

    @staticmethod
    def _matched_terms(query: str, snippet: str) -> list[str]:
        query_terms = {w.lower() for w in re.findall(r"\w+", query) if len(w) > 1}
        snippet_terms = {w.lower() for w in re.findall(r"\w+", snippet)}
        return sorted(query_terms & snippet_terms)

    @classmethod
    def _to_results(
        cls, rows: list[dict], query: str, keyword: bool, semantic: bool
    ) -> list[dict]:
        results = []
        for row in rows:
            snippet = row.get("snippet", "")
            results.append(
                {
                    "document_id": row["document_id"],
                    "title": row["title"],
                    "snippet": snippet,
                    "score": round(float(row["score"]), 6),
                    "matched_terms": cls._matched_terms(query, snippet),
                    "keyword_score": round(row["keyword_score"], 6)
                    if "keyword_score" in row
                    else (round(row["score"], 6) if keyword and not semantic else None),
                    "semantic_score": round(row["semantic_score"], 6)
                    if "semantic_score" in row
                    else (round(row["score"], 6) if semantic and not keyword else None),
                    "rerank_score": None,
                }
            )
        return results
