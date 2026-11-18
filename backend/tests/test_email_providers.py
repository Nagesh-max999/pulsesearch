import logging
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.email.base import EmailError
from app.services.email.console_provider import ConsoleEmailProvider
from app.services.email.factory import get_email_provider
from app.services.email.smtp_provider import SMTPEmailProvider


@pytest.mark.asyncio
async def test_console_provider_logs_the_email(caplog):
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO):
        await provider.send("someone@example.com", "Test subject", "Test body")

    assert any(
        "someone@example.com" in r.message and "Test subject" in r.message
        for r in caplog.records
    )


def _settings(**overrides) -> Settings:
    defaults = {"smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_use_tls": True}
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_smtp_provider_sends_via_starttls_and_login():
    provider = SMTPEmailProvider(
        _settings(smtp_username="user@example.com", smtp_password="secret")
    )
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp) as mock_smtp_class:
        await provider.send("to@example.com", "Subject line", "Body text")

    mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=10)
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("user@example.com", "secret")
    mock_smtp.send_message.assert_called_once()
    sent_message = mock_smtp.send_message.call_args.args[0]
    assert sent_message["To"] == "to@example.com"
    assert sent_message["Subject"] == "Subject line"


@pytest.mark.asyncio
async def test_smtp_provider_skips_login_without_credentials():
    provider = SMTPEmailProvider(_settings(smtp_username=""))
    mock_smtp = MagicMock()
    mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp.__exit__ = MagicMock(return_value=False)

    with patch("smtplib.SMTP", return_value=mock_smtp):
        await provider.send("to@example.com", "Subject", "Body")

    mock_smtp.login.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_provider_wraps_connection_failure():
    provider = SMTPEmailProvider(_settings())

    with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
        with pytest.raises(EmailError):
            await provider.send("to@example.com", "Subject", "Body")


def test_factory_returns_console_provider_by_default(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.delenv("SMTP_HOST", raising=False)
    get_settings.cache_clear()
    get_email_provider.cache_clear()
    try:
        provider = get_email_provider()
        assert isinstance(provider, ConsoleEmailProvider)
    finally:
        get_settings.cache_clear()
        get_email_provider.cache_clear()


def test_factory_returns_smtp_provider_when_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    get_settings.cache_clear()
    get_email_provider.cache_clear()
    try:
        provider = get_email_provider()
        assert isinstance(provider, SMTPEmailProvider)
    finally:
        monkeypatch.delenv("SMTP_HOST", raising=False)
        get_settings.cache_clear()
        get_email_provider.cache_clear()
