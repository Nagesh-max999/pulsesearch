from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)

# Read-replica routing: when DATABASE_URL_REPLICA is set, read-only endpoints
# (search, document listing/detail) use a session bound to it instead of the
# primary, taking read load off the instance writes go through. The read/write
# split in api/deps.py (get_db vs get_db_read) is wired and exercised today
# either way — when no replica is configured, get_db_read just reuses the
# primary's own engine/pool rather than opening a second, redundant pool to
# the same database.
if settings.database_url_replica:
    replica_engine = create_async_engine(
        settings.database_url_replica,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )
    AsyncSessionReplica = async_sessionmaker(
        bind=replica_engine,
        expire_on_commit=False,
        autoflush=False,
    )
else:
    AsyncSessionReplica = AsyncSessionLocal


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_db_read() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionReplica() as session:
        yield session
