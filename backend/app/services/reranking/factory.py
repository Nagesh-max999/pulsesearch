from functools import lru_cache

from app.services.reranking.base import RerankerProvider
from app.services.reranking.cross_encoder_provider import CrossEncoderReranker


@lru_cache
def get_reranker_provider() -> RerankerProvider:
    return CrossEncoderReranker()
