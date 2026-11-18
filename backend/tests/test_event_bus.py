import asyncio
import uuid

import pytest

from app.services.event_bus import DocumentEventBus

pytestmark = pytest.mark.asyncio


async def _start_waiting(agen):
    """Kicks off consumption of an async generator in the background and waits
    long enough for the underlying Redis SUBSCRIBE to actually register —
    async generators are lazy, so nothing happens until __anext__() is first
    awaited, and publishing before that point would be lost (pub/sub has no
    message replay)."""
    task = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.2)
    return task


async def _await_event(task, timeout: float = 5.0) -> dict:
    return await asyncio.wait_for(task, timeout=timeout)


async def test_publish_document_status_reaches_document_subscriber(redis_client):
    bus = DocumentEventBus(redis_client)
    document_id = uuid.uuid4()
    subscriber = bus.subscribe(document_id)
    task = await _start_waiting(subscriber)

    await bus.publish(document_id, "COMPLETED", "done")

    event = await _await_event(task)
    assert event["type"] == "document_status"
    assert event["document_id"] == str(document_id)
    assert event["status"] == "COMPLETED"
    assert event["message"] == "done"
    await subscriber.aclose()


async def test_publish_document_status_also_reaches_user_subscriber_when_user_id_given(
    redis_client,
):
    bus = DocumentEventBus(redis_client)
    document_id = uuid.uuid4()
    user_id = uuid.uuid4()
    subscriber = bus.subscribe_user(user_id)
    task = await _start_waiting(subscriber)

    await bus.publish(document_id, "PROCESSING", "working", user_id=user_id)

    event = await _await_event(task)
    assert event["type"] == "document_status"
    assert event["document_id"] == str(document_id)
    assert event["status"] == "PROCESSING"
    await subscriber.aclose()


async def test_publish_document_status_without_user_id_does_not_reach_any_user_channel(
    redis_client,
):
    bus = DocumentEventBus(redis_client)
    document_id = uuid.uuid4()
    user_id = uuid.uuid4()
    subscriber = bus.subscribe_user(user_id)
    task = await _start_waiting(subscriber)

    await bus.publish(document_id, "PROCESSING", "working")  # no user_id

    with pytest.raises(TimeoutError):
        await _await_event(task, timeout=0.5)
    task.cancel()
    await subscriber.aclose()


async def test_publish_search_reaches_user_subscriber(redis_client):
    bus = DocumentEventBus(redis_client)
    user_id = uuid.uuid4()
    subscriber = bus.subscribe_user(user_id)
    task = await _start_waiting(subscriber)

    await bus.publish_search(user_id, "connection pooling", "HYBRID", 3)

    event = await _await_event(task)
    assert event["type"] == "search"
    assert event["query"] == "connection pooling"
    assert event["mode"] == "HYBRID"
    assert event["result_count"] == 3
    await subscriber.aclose()


async def test_user_channels_are_isolated_between_users(redis_client):
    bus = DocumentEventBus(redis_client)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    subscriber_b = bus.subscribe_user(user_b)
    task = await _start_waiting(subscriber_b)

    await bus.publish_search(user_a, "only for a", "KEYWORD", 1)

    with pytest.raises(TimeoutError):
        await _await_event(task, timeout=0.5)
    task.cancel()
    await subscriber_b.aclose()


async def test_events_endpoint_requires_auth(client):
    resp = await client.get("/api/events")
    assert resp.status_code == 401
