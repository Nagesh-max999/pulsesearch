from abc import ABC, abstractmethod


class AIAnswerError(Exception):
    """Raised when an AI answer can't be produced (missing config, API
    failure, or the model declining to answer)."""


class AIAnswerProvider(ABC):
    """Interface AI-answer backends must implement.

    Same reasoning as EmbeddingProvider/RerankerProvider: the rest of the app
    depends only on this interface, so the concrete backend is swappable via
    configuration without touching call sites.
    """

    @abstractmethod
    async def answer(self, question: str, context_chunks: list[dict]) -> str:
        """Synthesizes an answer to `question` grounded in `context_chunks`.

        Each chunk is {"title": str, "content": str}. Implementations must
        instruct the model to answer only from this context and to say so
        plainly when the context doesn't contain an answer, rather than
        filling the gap from outside knowledge.
        """
