import asyncio
import logging
import threading

from app.core.config import get_settings
from app.services.reranking.base import RerankerError, RerankerProvider

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model_cache: dict[str, object] = {}


def _load_model(model_name: str):
    """Loads (and caches) the cross-encoder model, guarded by a real lock.

    Mirrors app/services/embeddings/sentence_transformer_provider.py's loader:
    functools.lru_cache is not single-flight under concurrency, so two threads
    racing to construct the same torch model at once can corrupt its state.
    """
    cached = _model_cache.get(model_name)
    if cached is not None:
        return cached
    with _model_lock:
        cached = _model_cache.get(model_name)
        if cached is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model %s", model_name)
            cached = CrossEncoder(model_name)
            _model_cache[model_name] = cached
        return cached


class CrossEncoderReranker(RerankerProvider):
    """Local, offline cross-encoder reranker — no API key or network dependency.

    Model inference is synchronous/CPU-bound, so it's run in a thread to avoid
    blocking the event loop, same as the embedding provider.
    """

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        self.model_name = model_name or settings.rerank_model_name

    def _model(self):
        try:
            return _load_model(self.model_name)
        except Exception as exc:  # model download/load failure
            raise RerankerError(f"Failed to load reranker model: {exc}") from exc

    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []

        def _score():
            model = self._model()
            pairs = [(query, candidate) for candidate in candidates]
            return model.predict(pairs)

        try:
            scores = await asyncio.to_thread(_score)
        except Exception as exc:
            raise RerankerError(f"Reranking failed: {exc}") from exc
        return [float(s) for s in scores]
