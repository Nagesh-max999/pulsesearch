import anthropic

from app.core.config import Settings, get_settings
from app.services.ai_answers.base import AIAnswerError, AIAnswerProvider

SYSTEM_PROMPT = """You answer questions using ONLY the document excerpts provided \
in the user's message. These excerpts come from the user's own uploaded documents.

Rules:
- Answer strictly from the provided excerpts. Never use outside knowledge, even if \
you're confident about the answer from training.
- If the excerpts don't contain enough information to answer the question, say so \
plainly and briefly — do not guess or fill the gap with outside knowledge.
- Be concise and direct.
- When you state a fact drawn from an excerpt, mention which document it came from \
by title.
"""


def _format_context(context_chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(context_chunks, start=1):
        parts.append(f"[Document {i}: {chunk['title']}]\n{chunk['content']}")
    return "\n\n".join(parts)


class AnthropicAnswerProvider(AIAnswerProvider):
    """AI answers backed by the Claude API (Messages endpoint)."""

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        if not settings.anthropic_api_key:
            raise AIAnswerError(
                "anthropic_api_key must be set when AI_ANSWERS_ENABLED=true"
            )
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.ai_answers_model
        self.max_tokens = settings.ai_answers_max_tokens
        self.effort = settings.ai_answers_effort

    async def answer(self, question: str, context_chunks: list[dict]) -> str:
        user_content = (
            f"Documents:\n\n{_format_context(context_chunks)}\n\nQuestion: {question}"
        )

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYSTEM_PROMPT,
                output_config={"effort": self.effort},
                messages=[{"role": "user", "content": user_content}],
            )
        except anthropic.AuthenticationError as exc:
            raise AIAnswerError(f"Invalid Anthropic API key: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise AIAnswerError(f"Anthropic API rate limit reached: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise AIAnswerError(f"Could not reach the Anthropic API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AIAnswerError(f"Anthropic API error ({exc.status_code}): {exc}") from exc

        if response.stop_reason == "refusal":
            raise AIAnswerError("The model declined to answer this question")

        return next((block.text for block in response.content if block.type == "text"), "")
