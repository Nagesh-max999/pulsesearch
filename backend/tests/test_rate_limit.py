import io

import pytest

from app.core.rate_limit import RateLimiter

pytestmark = pytest.mark.asyncio


async def test_rate_limiter_allows_up_to_the_limit(redis_client):
    limiter = RateLimiter(redis_client)

    for _ in range(3):
        allowed, retry_after = await limiter.check(
            "test-scope", "user-1", limit=3, window_seconds=60
        )
        assert allowed
        assert retry_after == 0


async def test_rate_limiter_blocks_after_the_limit(redis_client):
    limiter = RateLimiter(redis_client)

    for _ in range(3):
        await limiter.check("test-scope", "user-2", limit=3, window_seconds=60)

    allowed, retry_after = await limiter.check("test-scope", "user-2", limit=3, window_seconds=60)
    assert not allowed
    assert retry_after > 0


async def test_rate_limiter_scopes_are_independent(redis_client):
    limiter = RateLimiter(redis_client)

    for _ in range(3):
        await limiter.check("scope-a", "user-3", limit=3, window_seconds=60)

    # A different scope for the same key has its own budget.
    allowed, _ = await limiter.check("scope-b", "user-3", limit=3, window_seconds=60)
    assert allowed


async def test_rate_limiter_keys_are_independent(redis_client):
    limiter = RateLimiter(redis_client)

    for _ in range(3):
        await limiter.check("test-scope", "user-4", limit=3, window_seconds=60)

    # A different key (different user) in the same scope has its own budget.
    allowed, _ = await limiter.check("test-scope", "user-5", limit=3, window_seconds=60)
    assert allowed


async def test_search_endpoint_returns_429_once_limit_exceeded(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_SEARCH_PER_MINUTE", "2")
    get_settings.cache_clear()
    # KEYWORD mode avoids the local embedding model entirely (HYBRID/SEMANTIC
    # cold-load it on first use, which can be slow enough to cross the 60s
    # rate-limit window between requests and make this test flaky).
    params = {"q": "test", "mode": "KEYWORD"}
    try:
        for _ in range(2):
            resp = await client.get("/api/search", params=params, headers=auth_headers)
            assert resp.status_code == 200

        limited = await client.get("/api/search", params=params, headers=auth_headers)
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers
    finally:
        get_settings.cache_clear()


async def test_upload_endpoint_returns_429_once_limit_exceeded(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        files = {"file": ("a.txt", io.BytesIO(b"first upload"), "text/plain")}
        first = await client.post("/api/documents", files=files, headers=auth_headers)
        assert first.status_code == 202

        files = {"file": ("b.txt", io.BytesIO(b"second upload"), "text/plain")}
        limited = await client.post("/api/documents", files=files, headers=auth_headers)
        assert limited.status_code == 429
    finally:
        get_settings.cache_clear()
