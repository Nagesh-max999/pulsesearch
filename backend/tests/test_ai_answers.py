from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest

from app.core.config import Settings, get_settings
from app.services.ai_answers.anthropic_provider import AnthropicAnswerProvider
from app.services.ai_answers.base import AIAnswerError
from app.services.ai_answers.factory import get_ai_answer_provider


def _settings(**overrides) -> Settings:
    defaults = {"anthropic_api_key": "sk-ant-test", "ai_answers_model": "claude-opus-5"}
    defaults.update(overrides)
    return Settings(**defaults)


def _text_response(text: str, stop_reason: str = "end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    return response


def _api_error(exc_class, status_code: int = 500):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    if exc_class is anthropic.APIConnectionError:
        return exc_class(request=request)
    return exc_class("boom", response=response, body=None)


def test_requires_api_key():
    with pytest.raises(AIAnswerError):
        AnthropicAnswerProvider(_settings(anthropic_api_key=""))


@pytest.mark.asyncio
async def test_answer_returns_text_from_response():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        return_value=_text_response("The answer is 42.")
    )

    answer = await provider.answer(
        "What is the answer?", [{"title": "doc.txt", "content": "some content"}]
    )

    assert answer == "The answer is 42."


@pytest.mark.asyncio
async def test_answer_passes_model_and_context_to_the_api():
    provider = AnthropicAnswerProvider(_settings(ai_answers_model="claude-opus-5"))
    mock_create = AsyncMock(return_value=_text_response("answer"))
    provider._client.messages.create = mock_create

    await provider.answer("my question", [{"title": "notes.txt", "content": "the content"}])

    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-5"
    user_message = call_kwargs["messages"][0]["content"]
    assert "notes.txt" in user_message
    assert "the content" in user_message
    assert "my question" in user_message


@pytest.mark.asyncio
async def test_answer_raises_on_refusal():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        return_value=_text_response("", stop_reason="refusal")
    )

    with pytest.raises(AIAnswerError):
        await provider.answer("question", [{"title": "a.txt", "content": "c"}])


@pytest.mark.asyncio
async def test_answer_wraps_authentication_error():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        side_effect=_api_error(anthropic.AuthenticationError, 401)
    )

    with pytest.raises(AIAnswerError):
        await provider.answer("question", [{"title": "a.txt", "content": "c"}])


@pytest.mark.asyncio
async def test_answer_wraps_rate_limit_error():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        side_effect=_api_error(anthropic.RateLimitError, 429)
    )

    with pytest.raises(AIAnswerError):
        await provider.answer("question", [{"title": "a.txt", "content": "c"}])


@pytest.mark.asyncio
async def test_answer_wraps_connection_error():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        side_effect=_api_error(anthropic.APIConnectionError)
    )

    with pytest.raises(AIAnswerError):
        await provider.answer("question", [{"title": "a.txt", "content": "c"}])


@pytest.mark.asyncio
async def test_answer_wraps_generic_status_error():
    provider = AnthropicAnswerProvider(_settings())
    provider._client.messages.create = AsyncMock(
        side_effect=_api_error(anthropic.APIStatusError, 500)
    )

    with pytest.raises(AIAnswerError):
        await provider.answer("question", [{"title": "a.txt", "content": "c"}])


def test_factory_returns_anthropic_provider(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    get_settings.cache_clear()
    get_ai_answer_provider.cache_clear()
    try:
        provider = get_ai_answer_provider()
        assert isinstance(provider, AnthropicAnswerProvider)
    finally:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        get_settings.cache_clear()
        get_ai_answer_provider.cache_clear()


def test_factory_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    get_ai_answer_provider.cache_clear()
    try:
        with pytest.raises(AIAnswerError):
            get_ai_answer_provider()
    finally:
        get_settings.cache_clear()
        get_ai_answer_provider.cache_clear()
