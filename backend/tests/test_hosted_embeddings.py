from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.services.embeddings.base import EmbeddingProviderError
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.hosted_provider import HostedEmbeddingProvider
from app.services.embeddings.sentence_transformer_provider import SentenceTransformerProvider


def _settings(**overrides) -> Settings:
    defaults = {
        "embedding_provider": "hosted",
        "embedding_api_base_url": "https://api.example.com/v1",
        "embedding_api_key": "sk-test",
        "embedding_api_model": "text-embedding-3-small",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_requires_base_url():
    with pytest.raises(EmbeddingProviderError):
        HostedEmbeddingProvider(_settings(embedding_api_base_url=""))


def test_requires_api_key():
    with pytest.raises(EmbeddingProviderError):
        HostedEmbeddingProvider(_settings(embedding_api_key=""))


@pytest.mark.asyncio
async def test_embed_texts_returns_vectors_in_input_order():
    provider = HostedEmbeddingProvider(_settings())
    response_json = {
        "data": [
            {"index": 1, "embedding": [0.2, 0.3]},
            {"index": 0, "embedding": [0.1, 0.1]},
        ]
    }
    mock_response = httpx.Response(
        200, json=response_json, request=httpx.Request("POST", "https://api.example.com/v1/embeddings")
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
        vectors = await provider.embed_texts(["a", "b"])

    assert vectors == [[0.1, 0.1], [0.2, 0.3]]
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["input"] == ["a", "b"]
    assert call_kwargs["headers"]["Authorization"] == "Bearer sk-test"


@pytest.mark.asyncio
async def test_embed_texts_empty_input_short_circuits():
    provider = HostedEmbeddingProvider(_settings())
    with patch("httpx.AsyncClient.post", new=AsyncMock()) as mock_post:
        result = await provider.embed_texts([])
    assert result == []
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_embed_query_wraps_embed_texts():
    provider = HostedEmbeddingProvider(_settings())
    response_json = {"data": [{"index": 0, "embedding": [0.5, 0.5]}]}
    mock_response = httpx.Response(
        200, json=response_json, request=httpx.Request("POST", "https://api.example.com/v1/embeddings")
    )

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        vector = await provider.embed_query("hello")

    assert vector == [0.5, 0.5]


@pytest.mark.asyncio
async def test_http_failure_raises_embedding_provider_error():
    provider = HostedEmbeddingProvider(_settings())
    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        with pytest.raises(EmbeddingProviderError):
            await provider.embed_texts(["a"])


@pytest.mark.asyncio
async def test_unexpected_response_shape_raises_embedding_provider_error():
    provider = HostedEmbeddingProvider(_settings())
    mock_response = httpx.Response(
        200, json={"unexpected": "shape"}, request=httpx.Request("POST", "https://api.example.com/v1/embeddings")
    )
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(EmbeddingProviderError):
            await provider.embed_texts(["a"])


def test_factory_returns_local_provider_by_default(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    get_settings.cache_clear()
    get_embedding_provider.cache_clear()
    try:
        provider = get_embedding_provider()
        assert isinstance(provider, SentenceTransformerProvider)
    finally:
        get_settings.cache_clear()
        get_embedding_provider.cache_clear()


def test_factory_returns_hosted_provider_when_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("EMBEDDING_PROVIDER", "hosted")
    monkeypatch.setenv("EMBEDDING_API_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    get_settings.cache_clear()
    get_embedding_provider.cache_clear()
    try:
        provider = get_embedding_provider()
        assert isinstance(provider, HostedEmbeddingProvider)
    finally:
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        monkeypatch.delenv("EMBEDDING_API_BASE_URL", raising=False)
        monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
        get_settings.cache_clear()
        get_embedding_provider.cache_clear()
