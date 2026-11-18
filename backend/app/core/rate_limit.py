import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.deps import get_current_user, get_redis_client
from app.core.config import Settings, get_settings
from app.models.user import User

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window rate limiter backed by Redis.

    Each (scope, key) pair gets a counter for the current window
    (`rate_limit:{scope}:{key}:{window_index}`), incremented atomically and
    given a TTL on first use so it self-expires — no separate cleanup job. A
    fixed window can allow a short burst right at the window boundary (up to
    ~2x the limit across the boundary), which a sliding-window or token-bucket
    algorithm would avoid; that precision isn't worth the extra Redis round
    trips for per-user API limits at this scale.

    On Redis errors this fails *open* (allows the request, logs a warning):
    Redis is already a hard dependency for the queue and cache, but a rate
    limiter protecting the API shouldn't itself become a reason the API goes
    down when Redis blips.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(
        self, scope: str, key: str, limit: int, window_seconds: int
    ) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        window_index = int(time.time() // window_seconds)
        redis_key = f"rate_limit:{scope}:{key}:{window_index}"

        try:
            pipe = self.redis.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds)
            count, _ = await pipe.execute()
        except RedisError as exc:
            logger.warning("Redis unavailable for rate limiting, failing open: %s", exc)
            return True, 0

        if count > limit:
            retry_after = window_seconds - int(time.time() % window_seconds)
            return False, max(retry_after, 1)
        return True, 0


def rate_limit(
    scope: str, limit_attr: str
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Builds a FastAPI dependency enforcing a per-user, per-minute rate limit.

    `limit_attr` names the Settings field holding the limit for this scope
    (e.g. "rate_limit_search_per_minute"), so each call site gets its own
    configurable budget without duplicating this function.
    """

    async def _check(
        current_user: User = Depends(get_current_user),
        redis: Redis = Depends(get_redis_client),
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not settings.rate_limit_enabled:
            return

        limit = getattr(settings, limit_attr)
        limiter = RateLimiter(redis)
        allowed, retry_after = await limiter.check(scope, str(current_user.id), limit, 60)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit} requests per minute for {scope}",
                headers={"Retry-After": str(retry_after)},
            )

    return _check


def rate_limit_by_ip(
    scope: str, limit_attr: str
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Same as rate_limit(), but keyed by client IP instead of the
    authenticated user — for endpoints that run *before* authentication
    exists, like forgot-password, where there's no user_id yet to key on.
    """

    async def _check(
        request: Request,
        redis: Redis = Depends(get_redis_client),
        settings: Settings = Depends(get_settings),
    ) -> None:
        if not settings.rate_limit_enabled:
            return

        limit = getattr(settings, limit_attr)
        key = request.client.host if request.client else "unknown"
        limiter = RateLimiter(redis)
        allowed, retry_after = await limiter.check(scope, key, limit, 60)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {limit} requests per minute for {scope}",
                headers={"Retry-After": str(retry_after)},
            )

    return _check
