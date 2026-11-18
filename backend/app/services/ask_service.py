import uuid

from app.core.config import Settings
from app.models.search_event import SearchMode
from app.services.ai_answers.base import AIAnswerProvider
from app.services.search_service import SearchService

NO_CONTEXT_ANSWER = "I couldn't find anything in your documents about that."


class AskService:
    """Answers a question by retrieving relevant context, then asking an LLM
    to synthesize an answer grounded in it — retrieval-augmented generation,
    built entirely out of the search pipeline that already exists here.

    Reusing SearchService (hybrid mode, reranked, relevance-floor filtered)
    for retrieval means this inherits every quality property that pipeline
    already has: a query with no genuinely relevant documents returns zero
    chunks, so the LLM is never even called — no context to hallucinate from,
    and no cost paid asking a model to answer from nothing.
    """

    def __init__(
        self,
        search_service: SearchService,
        answer_provider: AIAnswerProvider,
        settings: Settings,
    ):
        self.search_service = search_service
        self.answer_provider = answer_provider
        self.settings = settings

    async def ask(self, user_id: uuid.UUID, question: str) -> dict:
        results, _total = await self.search_service.search(
            user_id,
            question,
            SearchMode.HYBRID,
            page=1,
            page_size=self.settings.ai_answers_context_chunks,
        )

        if not results:
            return {"question": question, "answer": NO_CONTEXT_ANSWER, "citations": []}

        context_chunks = [{"title": r["title"], "content": r["snippet"]} for r in results]
        answer_text = await self.answer_provider.answer(question, context_chunks)

        citations = [
            {"document_id": r["document_id"], "title": r["title"], "snippet": r["snippet"]}
            for r in results
        ]
        return {"question": question, "answer": answer_text, "citations": citations}
