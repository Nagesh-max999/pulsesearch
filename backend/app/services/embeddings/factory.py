from functools import lru_cache

from app.core.config import get_settings
from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.hosted_provider import HostedEmbeddingProvider
from app.services.embeddings.sentence_transformer_provider import SentenceTransformerProvider


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "hosted":
        return HostedEmbeddingProvider(settings)
    return SentenceTransformerProvider()
