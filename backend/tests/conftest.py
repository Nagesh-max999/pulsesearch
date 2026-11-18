import asyncio
import os
import uuid

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://pulsesearch:pulsesearch@localhost:5433/pulsesearch_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/1")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("UPLOAD_DIR", "./test_uploads")
# Reranking and rate limiting are real network/model-load or throughput concerns
# in production but would make the suite slow (extra model download) or flaky
# (fixed request budgets) if left on by default; individual tests opt back in.
os.environ.setdefault("RERANK_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Auto-seeding demo documents on registration would enqueue extra jobs and
# create extra documents for every test that registers a user (most of them),
# breaking exact-count assertions elsewhere; individual tests opt back in.
os.environ.setdefault("SEED_DEMO_DOCUMENTS", "false")
# AI answers call a real, paid external API — never on by default in tests.
# Tests that exercise the /api/ask route override its provider dependency
# with a stub instead of enabling this and hitting Anthropic for real.
os.environ.setdefault("AI_ANSWERS_ENABLED", "false")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_arq_pool, get_db, get_db_read, get_redis_client
from app.core.config import get_settings
from app.core.db import Base
from app.main import create_app


class FakeArqPool:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple]] = []

    async def enqueue_job(self, function: str, *args):
        self.enqueued.append((function, args))
        return None


async def _create_schema() -> None:
    eng = create_async_engine(get_settings().database_url)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await eng.dispose()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Creates the test schema once, on a throwaway event loop of its own.

    Deliberately NOT an async fixture: pytest-asyncio gives each test function its
    own event loop by default, but asyncpg connections/engines are bound to the loop
    that created them. A session-scoped *async* engine fixture would be reused across
    those per-test loops and asyncpg raises "another operation is in progress" /
    "Task attached to a different loop". Running schema setup via asyncio.run() here
    keeps it fully isolated; the per-test `db_session` fixture below creates its own
    engine on the test's own loop.
    """
    asyncio.run(_create_schema())


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(get_settings().database_url)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def fake_arq_pool():
    return FakeArqPool()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession, redis_client: Redis, fake_arq_pool: FakeArqPool):
    application = create_app()

    async def _get_db():
        yield db_session

    async def _get_redis():
        yield redis_client

    async def _get_arq_pool():
        return fake_arq_pool

    application.dependency_overrides[get_db] = _get_db
    application.dependency_overrides[get_db_read] = _get_db
    application.dependency_overrides[get_redis_client] = _get_redis
    application.dependency_overrides[get_arq_pool] = _get_arq_pool
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    password = "supersecret123"
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": password, "full_name": "Test User"}
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    return {"email": email, "password": password, "token": token, "id": me.json()["id"]}


@pytest_asyncio.fixture
async def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['token']}"}
