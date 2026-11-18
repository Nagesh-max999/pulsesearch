import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.security import hash_password
from app.repositories.password_reset_token_repo import PasswordResetTokenRepository
from app.repositories.user_repo import UserRepository
from app.services.email.base import EmailProvider

RESET_EMAIL_SUBJECT = "Reset your PulseSearch password"


class InvalidResetTokenError(Exception):
    pass


def _hash_token(raw_token: str) -> str:
    # sha256, not bcrypt: this is a high-entropy random token (256 bits),
    # not a low-entropy human password — nothing here is guessable enough to
    # need a slow, salted KDF, and a fast hash is what lets lookup-by-hash
    # use a plain index instead of checking every row.
    return hashlib.sha256(raw_token.encode()).hexdigest()


class PasswordResetService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: PasswordResetTokenRepository,
        email_provider: EmailProvider,
        settings: Settings,
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.email_provider = email_provider
        self.settings = settings

    async def request_reset(self, email: str) -> None:
        """Silently no-ops for an unknown email — the caller (the route)
        always returns the same generic response either way, so a bad actor
        can't use this endpoint to discover which emails have accounts."""
        user = await self.user_repo.get_by_email(email)
        if user is None:
            return

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=self.settings.password_reset_token_ttl_minutes
        )
        await self.token_repo.create(user.id, _hash_token(raw_token), expires_at)

        reset_link = f"{self.settings.frontend_base_url}/reset-password?token={raw_token}"
        body = (
            f"Someone requested a password reset for your PulseSearch account.\n\n"
            f"Reset your password: {reset_link}\n\n"
            f"This link expires in {self.settings.password_reset_token_ttl_minutes} minutes. "
            f"If you didn't request this, you can safely ignore this email."
        )
        await self.email_provider.send(user.email, RESET_EMAIL_SUBJECT, body)

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token = await self.token_repo.get_valid_by_hash(_hash_token(raw_token))
        if token is None:
            raise InvalidResetTokenError("This reset link is invalid or has expired.")

        user = await self.user_repo.get_by_id(token.user_id)
        if user is None:
            raise InvalidResetTokenError("This reset link is invalid or has expired.")

        await self.user_repo.update_password(user, hash_password(new_password))
        await self.token_repo.mark_used(token)
