from abc import ABC, abstractmethod


class RerankerError(Exception):
    """Raised when the reranker fails (model load, inference error, etc.)."""


class RerankerProvider(ABC):
    """Interface all rerankers must implement.

    A reranker scores (query, candidate) pairs directly — unlike the bi-encoder
    used for retrieval, which embeds query and document independently, a
    cross-encoder-style reranker attends over both texts jointly. That makes it
    far more accurate at judging relevance, at the cost of being too slow to run
    over an entire corpus — so it's used as a second pass over the retrieval
    stage's top candidates only.
    """

    @abstractmethod
    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        """Score each candidate's relevance to the query.

        Returns one float per candidate, same order as input — higher is more
        relevant. Not necessarily bounded to [0, 1]; callers should only use
        these scores for ordering, not as an absolute measure.
        """
