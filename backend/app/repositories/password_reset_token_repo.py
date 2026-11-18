import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset_token import PasswordResetToken


class PasswordResetTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_valid_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Returns the token only if it exists, hasn't been used, and hasn't
        expired — anything else should be treated as "invalid token" by the
        caller, without distinguishing why (not found vs. expired vs. reused
        all look the same to whoever is trying to guess a valid one)."""
        result = await self.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if token is None or token.used_at is not None:
            return None
        if token.expires_at < datetime.now(UTC):
            return None
        return token

    async def mark_used(self, token: PasswordResetToken) -> None:
        token.used_at = datetime.now(UTC)
        await self.session.flush()
