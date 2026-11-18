import logging

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_redis_client

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/api/health")
async def health(
    session: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis_client)
):
    checks = {"database": "unknown", "redis": "unknown"}
    healthy = True

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        checks["database"] = "unavailable"
        healthy = False
        logger.error("Database health check failed: %s", exc)

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except RedisError as exc:
        checks["redis"] = "unavailable"
        healthy = False
        logger.error("Redis health check failed: %s", exc)

    return {"status": "ok" if healthy else "degraded", "checks": checks}
