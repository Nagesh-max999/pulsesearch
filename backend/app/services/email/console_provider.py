import logging

from app.services.email.base import EmailProvider

logger = logging.getLogger(__name__)


class ConsoleEmailProvider(EmailProvider):
    """Default, zero-config email backend: logs the email instead of sending
    it. Used automatically whenever SMTP_HOST isn't set, so the
    forgot-password flow works out of the box in local dev — copy the reset
    link out of the log — without requiring real mail credentials. Never
    appropriate for production; SMTPEmailProvider is what actually delivers.
    """

    async def send(self, to: str, subject: str, body_text: str) -> None:
        logger.info(
            "Email not sent (no SMTP_HOST configured) — logging instead.\n"
            "To: %s\nSubject: %s\n%s",
            to,
            subject,
            body_text,
        )
