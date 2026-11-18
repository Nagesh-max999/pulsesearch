import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def _channel(document_id: uuid.UUID) -> str:
    return f"doc-events:{document_id}"


def _user_channel(user_id: uuid.UUID) -> str:
    return f"user-events:{user_id}"


class DocumentEventBus:
    """Publishes/subscribes to real activity over Redis pub/sub — document
    processing status (per-document channel) and, more broadly, anything a
    user's own dashboard should reflect live (per-user channel: document
    status changes plus search activity).

    This is how the background worker's real processing state, and the API's
    own request handling, reach the SSE endpoints — no frontend polling or
    simulated timers involved anywhere in this path.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish(
        self,
        document_id: uuid.UUID,
        status: str,
        message: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        payload = {
            "type": "document_status",
            "document_id": str(document_id),
            "status": status,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            await self.redis.publish(_channel(document_id), json.dumps(payload))
            if user_id is not None:
                await self.redis.publish(_user_channel(user_id), json.dumps(payload))
        except RedisError as exc:
            logger.warning("Failed to publish document event: %s", exc)

    async def publish_search(
        self, user_id: uuid.UUID, query: str, mode: str, result_count: int
    ) -> None:
        payload = {
            "type": "search",
            "query": query,
            "mode": mode,
            "result_count": result_count,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        try:
            await self.redis.publish(_user_channel(user_id), json.dumps(payload))
        except RedisError as exc:
            logger.warning("Failed to publish search event: %s", exc)

    async def subscribe(self, document_id: uuid.UUID) -> AsyncGenerator[dict, None]:
        async for event in self._subscribe(_channel(document_id)):
            yield event

    async def subscribe_user(self, user_id: uuid.UUID) -> AsyncGenerator[dict, None]:
        async for event in self._subscribe(_user_channel(user_id)):
            yield event

    async def _subscribe(self, channel: str) -> AsyncGenerator[dict, None]:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
