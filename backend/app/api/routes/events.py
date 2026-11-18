import json

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user_sse, get_redis_client
from app.models.user import User
from app.services.event_bus import DocumentEventBus

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def user_events(
    current_user: User = Depends(get_current_user_sse),
    redis: Redis = Depends(get_redis_client),
):
    """User-scoped live activity feed: every document status transition and
    every search, across all of the user's documents — not just the single
    document a document-detail page happens to have open. This is what lets
    the dashboard's aggregate numbers (total/processing/completed, search
    counts) update themselves in real time instead of only refreshing on
    the next page load.
    """
    event_bus = DocumentEventBus(redis)

    async def event_generator():
        async for event in event_bus.subscribe_user(current_user.id):
            yield {"event": event.get("type", "message"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())
