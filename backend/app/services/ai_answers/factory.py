from functools import lru_cache

from app.services.ai_answers.anthropic_provider import AnthropicAnswerProvider
from app.services.ai_answers.base import AIAnswerProvider


@lru_cache
def get_ai_answer_provider() -> AIAnswerProvider:
    return AnthropicAnswerProvider()
