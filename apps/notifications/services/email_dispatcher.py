"""
Email Dispatcher Service.
Sends multipart (HTML + plain text) messages via Django's configured email backend
and distinguishes backend acceptance from uncertain transport outcomes.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def _safe_error_message(exc: Exception) -> str:
    message = str(exc)
    for secret in (
        getattr(settings, "EMAIL_HOST_PASSWORD", ""),
        getattr(settings, "EMAIL_HOST_USER", ""),
    ):
        if secret:
            message = message.replace(secret, "[redacted]")
    return f"{type(exc).__name__}: {message}"[:2000]


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str,
    from_email: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[bool, str, str, bool]:
    """
    Send a multipart HTML + text email using Django's email infrastructure.
    Returns:
        (accepted: bool, provider_message_id: str, error_message: str, uncertain: bool)
    """
    sender = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@college.edu")

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content or html_content,
            from_email=sender,
            to=[to_email],
            headers=headers,
        )
        if html_content:
            msg.attach_alternative(html_content, "text/html")

        # send() returns the number of successfully delivered messages (0 or 1)
        sent_count = msg.send(fail_silently=False)

        if sent_count > 0:
            logger.info("Email accepted by the configured backend.")
            return True, "", "", False
        else:
            err = "Email backend did not accept the message for delivery (returned 0)."
            logger.error("Email delivery failed: backend returned no accepted messages.")
            return False, "", err, False

    except Exception as exc:
        err = _safe_error_message(exc)
        logger.error("Exception during email dispatch: %s", err)
        return False, "", err, True
