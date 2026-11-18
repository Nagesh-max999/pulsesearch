import uuid
from collections.abc import AsyncGenerator

from arq import ArqRedis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, get_db_read
from app.core.redis import get_redis
from app.core.security import TokenError, decode_access_token
from app.models.user import User
from app.repositories.chunk_repo import ChunkRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.search_event_repo import SearchEventRepository
from app.repositories.user_repo import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool


async def get_redis_client() -> AsyncGenerator[Redis, None]:
    client = get_redis()
    try:
        yield client
    finally:
        await client.aclose()


async def _resolve_user(token: str | None, session: AsyncSession) -> User:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user_repo = UserRepository(session)
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject"
        ) from exc

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    return await _resolve_user(token, session)


async def get_current_user_sse(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Same as get_current_user, but also accepts ?token=... since the browser's
    EventSource API cannot set an Authorization header."""
    token = credentials.credentials if credentials else request.query_params.get("token")
    return await _resolve_user(token, session)


def get_user_repo(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


def get_document_repo(session: AsyncSession = Depends(get_db)) -> DocumentRepository:
    return DocumentRepository(session)


def get_document_repo_read(session: AsyncSession = Depends(get_db_read)) -> DocumentRepository:
    """Same repository, bound to the read-replica session (see core/db.py) —
    use for GET/list endpoints that don't need read-your-writes consistency
    within the same request."""
    return DocumentRepository(session)


def get_chunk_repo(session: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(session)


def get_chunk_repo_read(session: AsyncSession = Depends(get_db_read)) -> ChunkRepository:
    return ChunkRepository(session)


def get_search_event_repo(session: AsyncSession = Depends(get_db)) -> SearchEventRepository:
    return SearchEventRepository(session)
