from functools import lru_cache

from app.core.config import get_settings
from app.services.email.base import EmailProvider
from app.services.email.console_provider import ConsoleEmailProvider
from app.services.email.smtp_provider import SMTPEmailProvider


@lru_cache
def get_email_provider() -> EmailProvider:
    settings = get_settings()
    if settings.smtp_host:
        return SMTPEmailProvider(settings)
    return ConsoleEmailProvider()
