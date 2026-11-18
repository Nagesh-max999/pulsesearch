import asyncio
import logging
import threading

from app.core.config import get_settings
from app.services.embeddings.base import EmbeddingProvider, EmbeddingProviderError

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model_cache: dict[str, object] = {}


def _load_model(model_name: str):
    """Loads (and caches) the model, guarded by a real lock.

    `functools.lru_cache` looks like it would do this, but it isn't single-flight
    under concurrency: the docs note concurrent cache misses can each call the
    wrapped function before the first result is stored. Two threads constructing
    the same SentenceTransformer/torch model at once corrupts its state (observed
    as "Cannot copy out of meta tensor" under concurrent first requests), so this
    uses an explicit lock instead.
    """
    cached = _model_cache.get(model_name)
    if cached is not None:
        return cached
    with _model_lock:
        cached = _model_cache.get(model_name)
        if cached is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s", model_name)
            cached = SentenceTransformer(model_name)
            _model_cache[model_name] = cached
        return cached


class SentenceTransformerProvider(EmbeddingProvider):
    """Local, offline embedding provider — no API key or network dependency.

    Model inference is synchronous/CPU-bound, so it's run in a thread to avoid
    blocking the event loop.
    """

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model_name
        self.dimension = settings.embedding_dim

    def _model(self):
        try:
            return _load_model(self.model_name)
        except Exception as exc:  # model download/load failure
            raise EmbeddingProviderError(f"Failed to load embedding model: {exc}") from exc

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        def _load_and_encode():
            model = self._model()
            return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

        try:
            # Loading the model (first call: downloads + loads, can take well over a
            # minute) and encoding are both run in a thread. Loading it directly on
            # the event loop would stall every other request in the process for as
            # long as that takes; lru_cache's internal lock keeps concurrent callers
            # from triggering redundant loads.
            vectors = await asyncio.to_thread(_load_and_encode)
        except Exception as exc:
            raise EmbeddingProviderError(f"Embedding generation failed: {exc}") from exc
        return [v.tolist() for v in vectors]

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0]
