from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings


def _send_message(recipient: str, otp: str) -> None:
    message = EmailMessage()
    message["Subject"] = "ShareM Int Xpo email verification code"
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message.set_content(
        "Your ShareM Int Xpo verification code is: "
        f"{otp}\n\nThis code expires in 10 minutes. "
        "If you did not create this account, you can ignore this email."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
        if settings.smtp_use_tls:
            client.starttls(context=context)
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(message)


async def send_verification_email(recipient: str, otp: str) -> None:
    await asyncio.to_thread(_send_message, recipient, otp)
