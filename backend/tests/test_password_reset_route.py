import logging
import re

import pytest

pytestmark = pytest.mark.asyncio


def _extract_token(log_text: str) -> str:
    match = re.search(r"token=([\w-]+)", log_text)
    assert match, f"no token found in logged email: {log_text}"
    return match.group(1)


async def test_forgot_password_returns_generic_response_for_unknown_email(client):
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 202
    assert "registered" in resp.json()["message"].lower()


async def test_forgot_password_returns_same_generic_response_for_known_email(
    client, registered_user
):
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": registered_user["email"]}
    )
    assert resp.status_code == 202
    assert "registered" in resp.json()["message"].lower()


async def test_forgot_password_logs_a_reset_email_by_default(client, registered_user, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.email.console_provider"):
        resp = await client.post(
            "/api/auth/forgot-password", json={"email": registered_user["email"]}
        )

    assert resp.status_code == 202
    assert any("reset-password?token=" in record.message for record in caplog.records)


async def test_full_reset_flow_end_to_end_through_http(client, registered_user, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.email.console_provider"):
        forgot_resp = await client.post(
            "/api/auth/forgot-password", json={"email": registered_user["email"]}
        )
    assert forgot_resp.status_code == 202

    logged_body = next(r.message for r in caplog.records if "reset-password?token=" in r.message)
    token = _extract_token(logged_body)

    reset_resp = await client.post(
        "/api/auth/reset-password",
        json={"token": token, "new_password": "aBrandNewPassword789"},
    )
    assert reset_resp.status_code == 200

    old_login = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": "aBrandNewPassword789"},
    )
    assert new_login.status_code == 200


async def test_reset_password_with_invalid_token_returns_400(client):
    resp = await client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "somenewpassword123"},
    )
    assert resp.status_code == 400


async def test_reset_password_rejects_short_password(client, registered_user, caplog):
    with caplog.at_level(logging.INFO, logger="app.services.email.console_provider"):
        await client.post(
            "/api/auth/forgot-password", json={"email": registered_user["email"]}
        )
    logged_body = next(r.message for r in caplog.records if "reset-password?token=" in r.message)
    token = _extract_token(logged_body)

    resp = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert resp.status_code == 422


async def test_forgot_password_returns_429_once_rate_limited(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_PER_MINUTE", "1")
    get_settings.cache_clear()
    try:
        first = await client.post(
            "/api/auth/forgot-password", json={"email": "a@example.com"}
        )
        assert first.status_code == 202

        limited = await client.post(
            "/api/auth/forgot-password", json={"email": "b@example.com"}
        )
        assert limited.status_code == 429
        assert "Retry-After" in limited.headers
    finally:
        get_settings.cache_clear()
