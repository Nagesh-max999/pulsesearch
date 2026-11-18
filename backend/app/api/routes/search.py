import time

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_chunk_repo_read, get_current_user, get_db, get_redis_client
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limit
from app.models.search_event import SearchMode
from app.models.user import User
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.search_event_repo import SearchEventRepository
from app.schemas.search import SearchResponse, SearchResultItem
from app.services.cache_service import SearchCache
from app.services.embeddings.factory import get_embedding_provider
from app.services.event_bus import DocumentEventBus
from app.services.reranking.factory import get_reranker_provider
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])
_search_rate_limit = rate_limit("search", "rate_limit_search_per_minute")


@router.get("", response_model=SearchResponse, dependencies=[Depends(_search_rate_limit)])
async def search(
    q: str = Query(min_length=1, max_length=500),
    mode: SearchMode = Query(default=SearchMode.HYBRID),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    chunk_repo: ChunkRepository = Depends(get_chunk_repo_read),
    redis: Redis = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    cache = SearchCache(redis, settings.search_cache_ttl_seconds)
    cached = await cache.get(current_user.id, mode.value, q, page, page_size)
    if cached is not None:
        return SearchResponse(**cached)

    start = time.perf_counter()
    reranker = get_reranker_provider() if settings.rerank_enabled else None
    service = SearchService(chunk_repo, get_embedding_provider(), settings, reranker)
    rows, total = await service.search(current_user.id, q, mode, page, page_size)
    latency_ms = (time.perf_counter() - start) * 1000

    event_repo = SearchEventRepository(session)
    await event_repo.record(current_user.id, q, mode, total, latency_ms)
    await session.commit()
    await DocumentEventBus(redis).publish_search(current_user.id, q, mode.value, total)

    response = SearchResponse(
        query=q,
        mode=mode,
        results=[SearchResultItem(**row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        latency_ms=round(latency_ms, 2),
    )
    await cache.set(current_user.id, mode.value, q, page, page_size, response.model_dump())
    return response
