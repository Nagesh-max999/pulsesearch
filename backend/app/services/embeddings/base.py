from abc import ABC, abstractmethod


class EmbeddingProviderError(Exception):
    """Raised when the embedding provider fails (timeout, missing credentials, etc.)."""


class EmbeddingProvider(ABC):
    """Interface all embedding backends must implement.

    Keeping the rest of the app dependent only on this interface means the concrete
    backend (local model, OpenAI, Cohere, ...) can be swapped via configuration alone.
    """

    dimension: int

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Must return vectors in the same order as input."""

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
