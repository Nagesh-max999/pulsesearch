import uuid

import pytest

from app.core.config import get_settings
from app.repositories.password_reset_token_repo import PasswordResetTokenRepository
from app.repositories.user_repo import UserRepository
from app.services.email.base import EmailProvider
from app.services.password_reset_service import InvalidResetTokenError, PasswordResetService

pytestmark = pytest.mark.asyncio


class _CapturingEmailProvider(EmailProvider):
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body_text: str) -> None:
        self.sent.append((to, subject, body_text))


def _extract_token(body_text: str) -> str:
    import re

    match = re.search(r"token=([\w-]+)", body_text)
    assert match, f"no token found in email body: {body_text}"
    return match.group(1)


async def _register(client, email="reset-target@example.com", password="originalpass123"):
    resp = await client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    assert resp.status_code == 201
    return email, password


async def test_request_reset_for_unknown_email_sends_nothing(db_session):
    email_provider = _CapturingEmailProvider()
    service = PasswordResetService(
        UserRepository(db_session),
        PasswordResetTokenRepository(db_session),
        email_provider,
        get_settings(),
    )

    await service.request_reset("nobody-has-this-email@example.com")

    assert email_provider.sent == []


async def test_request_reset_for_known_email_sends_a_reset_link(client, db_session):
    email, _ = await _register(client)
    email_provider = _CapturingEmailProvider()
    service = PasswordResetService(
        UserRepository(db_session),
        PasswordResetTokenRepository(db_session),
        email_provider,
        get_settings(),
    )

    await service.request_reset(email)

    assert len(email_provider.sent) == 1
    to, subject, body = email_provider.sent[0]
    assert to == email
    assert "reset" in subject.lower()
    assert "/reset-password?token=" in body


async def test_reset_password_with_valid_token_updates_password_and_marks_used(
    client, db_session
):
    email, old_password = await _register(client)
    email_provider = _CapturingEmailProvider()
    service = PasswordResetService(
        UserRepository(db_session),
        PasswordResetTokenRepository(db_session),
        email_provider,
        get_settings(),
    )
    await service.request_reset(email)
    raw_token = _extract_token(email_provider.sent[0][2])

    await service.reset_password(raw_token, "brandnewpassword456")

    # Old password no longer works, new one does — checked via the real
    # login endpoint, not by inspecting the hash directly.
    old_login = await client.post(
        "/api/auth/login", json={"email": email, "password": old_password}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/auth/login", json={"email": email, "password": "brandnewpassword456"}
    )
    assert new_login.status_code == 200


async def test_reset_password_token_cannot_be_reused(client, db_session):
    email, _ = await _register(client)
    email_provider = _CapturingEmailProvider()
    service = PasswordResetService(
        UserRepository(db_session),
        PasswordResetTokenRepository(db_session),
        email_provider,
        get_settings(),
    )
    await service.request_reset(email)
    raw_token = _extract_token(email_provider.sent[0][2])

    await service.reset_password(raw_token, "firstnewpassword")

    with pytest.raises(InvalidResetTokenError):
        await service.reset_password(raw_token, "secondnewpassword")


async def test_reset_password_with_garbage_token_raises(db_session):
    service = PasswordResetService(
        UserRepository(db_session),
        PasswordResetTokenRepository(db_session),
        _CapturingEmailProvider(),
        get_settings(),
    )

    with pytest.raises(InvalidResetTokenError):
        await service.reset_password("not-a-real-token", "somenewpassword")


async def test_reset_password_with_expired_token_raises(client, db_session, monkeypatch):
    from app.core.config import get_settings as _get_settings

    monkeypatch.setenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "0")
    _get_settings.cache_clear()
    try:
        email, _ = await _register(client, email=f"expiring-{uuid.uuid4().hex[:8]}@example.com")
        email_provider = _CapturingEmailProvider()
        service = PasswordResetService(
            UserRepository(db_session),
            PasswordResetTokenRepository(db_session),
            email_provider,
            _get_settings(),
        )
        await service.request_reset(email)
        raw_token = _extract_token(email_provider.sent[0][2])

        with pytest.raises(InvalidResetTokenError):
            await service.reset_password(raw_token, "somenewpassword")
    finally:
        _get_settings.cache_clear()
