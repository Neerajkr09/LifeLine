"""
Outbound email delivery.

If SMTP_HOST is unset (the default), OTPs are logged to the server console
instead of emailed -- this lets the whole registration/verification flow be
exercised end-to-end in local development without needing real SMTP
credentials. Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD in .env to send real
email in staging/production.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.email")


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)


def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    subject = "Your Blood Donor Platform verification code"
    body = (
        f"Your verification code is: {otp}\n\n"
        f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes and is for: {purpose}.\n"
        "If you did not request this, you can safely ignore this email."
    )

    if not _smtp_configured():
        # Dev-mode fallback: make the OTP visible in server logs so the flow
        # is fully testable without real email infrastructure.
        logger.warning(
            "[DEV MODE - SMTP not configured] OTP for %s (%s): %s", to_email, purpose, otp
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls(context=context)
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)
    logger.info("OTP email sent to %s for purpose=%s", to_email, purpose)
