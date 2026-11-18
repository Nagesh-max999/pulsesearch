import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis

from app.api.deps import get_chunk_repo_read, get_current_user, get_redis_client
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limit
from app.models.user import User
from app.repositories.chunk_repo import ChunkRepository
from app.schemas.qa import AskResponse
from app.services.ai_answers.base import AIAnswerError, AIAnswerProvider
from app.services.ai_answers.factory import get_ai_answer_provider
from app.services.ask_service import AskService
from app.services.cache_service import AskCache
from app.services.embeddings.factory import get_embedding_provider
from app.services.reranking.factory import get_reranker_provider
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/ask", tags=["ask"])
_ask_rate_limit = rate_limit("ask", "rate_limit_ask_per_minute")


def get_ai_answer_provider_optional(
    settings: Settings = Depends(get_settings),
) -> AIAnswerProvider | None:
    """None means "not usable right now" — disabled by config, or enabled but
    misconfigured (e.g. no API key). The route turns either into a clean 503
    instead of letting AIAnswerError surface as an unhandled 500.

    Wrapping the factory as its own dependency (rather than calling it inline
    the way the embedding/reranker factories are called elsewhere) is what
    lets tests swap in a stub provider via dependency_overrides for a real
    end-to-end check of this route without calling the actual Anthropic API.
    """
    if not settings.ai_answers_enabled:
        return None
    try:
        return get_ai_answer_provider()
    except AIAnswerError:
        return None


@router.get("", response_model=AskResponse, dependencies=[Depends(_ask_rate_limit)])
async def ask(
    q: str = Query(min_length=1, max_length=500),
    current_user: User = Depends(get_current_user),
    chunk_repo: ChunkRepository = Depends(get_chunk_repo_read),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
    answer_provider: AIAnswerProvider | None = Depends(get_ai_answer_provider_optional),
):
    if answer_provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "AI answers are not enabled on this deployment. Set "
                "AI_ANSWERS_ENABLED=true and ANTHROPIC_API_KEY to use this feature."
            ),
        )

    cache = AskCache(redis, settings.ai_answers_cache_ttl_seconds)
    cached = await cache.get(current_user.id, q)
    if cached is not None:
        return AskResponse(**cached)

    reranker = get_reranker_provider() if settings.rerank_enabled else None
    search_service = SearchService(chunk_repo, get_embedding_provider(), settings, reranker)
    ask_service = AskService(search_service, answer_provider, settings)

    start = time.perf_counter()
    try:
        result = await ask_service.ask(current_user.id, q)
    except AIAnswerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    response = AskResponse(**result, latency_ms=latency_ms)
    await cache.set(current_user.id, q, response.model_dump())
    return response
