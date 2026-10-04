"""SMTP delivery. Tokens are never logged or returned by the API."""
import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from app.core.config import settings


async def send_auth_email(recipient: str, subject: str, body: str) -> None:
    await send_email(recipient, subject, body)


async def send_email(recipient: str, subject: str, body: str, *, reply_to: str | None = None) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise RuntimeError("SMTP delivery is not configured")
    if settings.SMTP_SSL and settings.SMTP_STARTTLS:
        raise RuntimeError("Choose SMTP_SSL or SMTP_STARTTLS, not both")

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = recipient
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    def deliver():
        context = ssl.create_default_context()
        if settings.SMTP_SSL:
            connection = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context)
        else:
            connection = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        with connection as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls(context=context)
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)

    await asyncio.to_thread(deliver)
