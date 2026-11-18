import httpx

from app.core.config import get_settings
from app.services.embeddings.base import EmbeddingProvider, EmbeddingProviderError


class HostedEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by a hosted, OpenAI-compatible /embeddings API.

    Works with OpenAI directly, or any OpenAI-compatible endpoint (Together,
    Groq, a self-hosted vLLM/TEI server, ...) by pointing embedding_api_base_url
    at it. Trades the local model's zero-cost/offline properties for higher
    embedding quality and no local CPU/RAM cost — the tradeoff documented in
    docs/architecture.md's "Future improvements" section.
    """

    def __init__(self, settings=None):
        settings = settings or get_settings()
        if not settings.embedding_api_base_url:
            raise EmbeddingProviderError(
                "embedding_api_base_url must be set when EMBEDDING_PROVIDER=hosted"
            )
        if not settings.embedding_api_key:
            raise EmbeddingProviderError(
                "embedding_api_key must be set when EMBEDDING_PROVIDER=hosted"
            )
        self.base_url = settings.embedding_api_base_url.rstrip("/")
        self.api_key = settings.embedding_api_key
        self.model = settings.embedding_api_model or settings.embedding_model_name
        self.dimension = settings.embedding_dim

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"input": texts, "model": self.model},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingProviderError(f"Hosted embedding request failed: {exc}") from exc

        body = response.json()
        try:
            # data isn't guaranteed to preserve input order across providers,
            # so sort by the index each provider is required to echo back.
            ordered = sorted(body["data"], key=lambda item: item["index"])
            return [item["embedding"] for item in ordered]
        except (KeyError, TypeError) as exc:
            raise EmbeddingProviderError(f"Unexpected embedding response shape: {exc}") from exc

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0]
