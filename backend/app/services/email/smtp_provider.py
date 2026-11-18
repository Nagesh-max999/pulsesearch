import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.services.email.base import EmailError, EmailProvider


class SMTPEmailProvider(EmailProvider):
    """Sends real email over SMTP — works with any provider that exposes an
    SMTP endpoint (Gmail, SES, Postmark, Mailgun, a self-hosted relay, ...),
    so there's no vendor-specific SDK to swap out later.

    smtplib is synchronous; every call runs in a thread rather than blocking
    the event loop, the same tradeoff the local embedding model and the S3
    storage provider make for their own blocking I/O.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    async def send(self, to: str, subject: str, body_text: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text)

        def _send() -> None:
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
                if self.settings.smtp_use_tls:
                    smtp.starttls()
                if self.settings.smtp_username:
                    smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)

        try:
            await asyncio.to_thread(_send)
        except (OSError, smtplib.SMTPException) as exc:
            raise EmailError(f"Failed to send email via SMTP: {exc}") from exc
