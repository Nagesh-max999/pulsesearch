import hashlib
import json
import logging
import uuid

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class SearchCache:
    """Caches search results in Redis.

    Key design: search:{user_id}:{mode}:{page}:{page_size}:{query_hash} — scoped per
    user so results never leak across accounts, and per mode/page so pagination and
    keyword/semantic/hybrid results don't collide. TTL is short (default 60s) because
    a newly-indexed document should become visible in search quickly. On any Redis
    error (down, timeout) we log and treat it as a cache miss rather than failing the
    request — caching is a performance optimization, not a correctness dependency.
    """

    def __init__(self, redis: Redis, ttl_seconds: int):
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(user_id: uuid.UUID, mode: str, query: str, page: int, page_size: int) -> str:
        query_hash = hashlib.sha256(query.strip().lower().encode()).hexdigest()[:16]
        return f"search:{user_id}:{mode}:{page}:{page_size}:{query_hash}"

    async def get(
        self, user_id: uuid.UUID, mode: str, query: str, page: int, page_size: int
    ) -> dict | None:
        key = self._key(user_id, mode, query, page, page_size)
        try:
            raw = await self.redis.get(key)
        except RedisError as exc:
            logger.warning("Redis unavailable for cache read: %s", exc)
            return None
        return json.loads(raw) if raw else None

    async def set(
        self,
        user_id: uuid.UUID,
        mode: str,
        query: str,
        page: int,
        page_size: int,
        payload: dict,
    ) -> None:
        key = self._key(user_id, mode, query, page, page_size)
        try:
            await self.redis.set(key, json.dumps(payload, default=str), ex=self.ttl_seconds)
        except RedisError as exc:
            logger.warning("Redis unavailable for cache write: %s", exc)


class AskCache:
    """Caches AI answers in Redis — same shape as SearchCache, but worth it
    even more here: an LLM call has a real per-request dollar cost, not just
    latency, so a repeated question should never pay for a second one within
    the TTL window.
    """

    def __init__(self, redis: Redis, ttl_seconds: int):
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(user_id: uuid.UUID, question: str) -> str:
        question_hash = hashlib.sha256(question.strip().lower().encode()).hexdigest()[:16]
        return f"ask:{user_id}:{question_hash}"

    async def get(self, user_id: uuid.UUID, question: str) -> dict | None:
        key = self._key(user_id, question)
        try:
            raw = await self.redis.get(key)
        except RedisError as exc:
            logger.warning("Redis unavailable for cache read: %s", exc)
            return None
        return json.loads(raw) if raw else None

    async def set(self, user_id: uuid.UUID, question: str, payload: dict) -> None:
        key = self._key(user_id, question)
        try:
            await self.redis.set(key, json.dumps(payload, default=str), ex=self.ttl_seconds)
        except RedisError as exc:
            logger.warning("Redis unavailable for cache write: %s", exc)
