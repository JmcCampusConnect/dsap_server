"""
Event Dispatcher Service.
Coordinates template lookup, recipient resolution, rendering, database idempotency,
transaction-safe email dispatch, failure recording, and manual retries.
"""

import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.notifications.models import (
    Notification,
    NotificationChannels,
    NotificationStatuses,
    NotificationTemplate,
)
from .email_dispatcher import send_email
from .recipient_resolver import (
    ResolvedRecipient,
    resolve_request_recipient,
    resolve_test_recipient,
)
from .template_renderer import render_template

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def build_event_context(
    request_obj,
    recipient: ResolvedRecipient,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build approved context dictionary for template rendering."""
    extra = extra_context or {}
    now = timezone.now()
    action_date_str = now.strftime("%Y-%m-%d %H:%M UTC")

    frontend_base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    if request_obj and getattr(request_obj, "id", None):
        portal_url = f"{frontend_base}/requests/my/{request_obj.id}"
    else:
        portal_url = frontend_base

    service_name = ""
    if request_obj and getattr(request_obj, "service_id", None):
        service_name = getattr(request_obj.service_id, "name", "")

    req_num = getattr(request_obj, "request_number", "") if request_obj else "TEST-REQ"
    current_status = getattr(request_obj, "current_status", "") if request_obj else "ACTIVE"

    return {
        "student_name": recipient.student_name or "",
        "register_number": recipient.register_number or "",
        "request_number": req_num,
        "service_name": service_name,
        "previous_status": str(extra.get("previous_status", "")),
        "new_status": str(extra.get("new_status", current_status)),
        "remarks": str(extra.get("remarks", "")),
        "action_date": str(extra.get("action_date", action_date_str)),
        "portal_url": portal_url,
    }


def dispatch_notification(
    event_code: str,
    request_obj=None,
    event_identifier: str | None = None,
    extra_context: dict[str, Any] | None = None,
    is_test: bool = False,
    test_recipient_email: str | None = None,
    admin_user=None,
) -> Notification | None:
    """
    Core notification dispatch routine.
    Idempotent by event_identifier + channel.
    """
    if not is_test and event_identifier:
        existing = Notification.objects.filter(
            event_identifier=event_identifier,
            channel=NotificationChannels.EMAIL,
        ).first()
        if existing:
            logger.info(
                "Duplicate notification skipped for event_identifier=%s (status=%s).",
                event_identifier,
                existing.status,
            )
            return existing

    template = NotificationTemplate.objects.filter(
        event_code=event_code,
        channel=NotificationChannels.EMAIL,
    ).first()
    if not template:
        logger.warning(
            "No EMAIL template found for event_code=%s; skipping request %s.",
            event_code,
            getattr(request_obj, "id", None),
        )
        return None
    if not template.is_active:
        logger.info(
            "Template for event_code=%s is inactive; skipping request %s.",
            event_code,
            getattr(request_obj, "id", None),
        )
        return None

    recipient = (
        resolve_test_recipient(test_recipient_email or "", admin_user)
        if is_test
        else resolve_request_recipient(request_obj)
    )
    event_id = event_identifier if not is_test else None
    base_record = {
        "request_id": request_obj,
        "user_id": recipient.user,
        "channel": NotificationChannels.EMAIL,
        "template_id": template,
        "recipient_email": recipient.email,
        "event_identifier": event_id,
        "event_code": event_code,
        "request_number_snapshot": getattr(request_obj, "request_number", ""),
        "is_test": is_test,
        "last_attempt_at": timezone.now(),
    }

    if not recipient.is_valid:
        logger.error(
            "Cannot dispatch event_code=%s: %s",
            event_code,
            recipient.error_message,
        )
        return _create_idempotent_notification(
            {
                **base_record,
                "subject": template.subject or "Notification",
                "message": template.template_body or "",
                "status": NotificationStatuses.FAILED,
                "delivery_error": recipient.error_message,
            },
            event_identifier=event_id,
        )[0]

    context = build_event_context(request_obj, recipient, extra_context)
    try:
        rendered_subject, rendered_html, rendered_text = render_template(
            subject_template=template.subject,
            body_template=template.template_body,
            context=context,
            sanitize=True,
        )
    except ValidationError as exc:
        logger.error("Invalid notification template for event %s: %s", event_code, exc)
        return _create_idempotent_notification(
            {
                **base_record,
                "subject": template.subject,
                "message": template.template_body,
                "status": NotificationStatuses.FAILED,
                "delivery_error": f"Template validation failed: {exc}",
            },
            event_identifier=event_id,
        )[0]

    notification, created = _create_idempotent_notification(
        {
            **base_record,
            "subject": rendered_subject,
            "message": rendered_html,
            "status": NotificationStatuses.SENDING,
        },
        event_identifier=event_id,
    )
    if not created:
        return notification

    accepted, provider_message_id, error_message, uncertain = send_email(
        to_email=recipient.email,
        subject=rendered_subject,
        html_content=rendered_html,
        text_content=rendered_text,
    )
    now = timezone.now()
    if accepted:
        notification.status = NotificationStatuses.SENT
    elif uncertain:
        notification.status = NotificationStatuses.UNCERTAIN
    else:
        notification.status = NotificationStatuses.FAILED
    notification.sent_at = now if accepted else None
    notification.last_attempt_at = now
    notification.provider_message_id = provider_message_id
    notification.delivery_error = "" if accepted else error_message
    notification.save(
        update_fields=[
            "status",
            "sent_at",
            "last_attempt_at",
            "provider_message_id",
            "delivery_error",
            "updated_at",
        ]
    )
    return notification


def _create_idempotent_notification(
    values: dict[str, Any],
    event_identifier: str | None,
) -> tuple[Notification, bool]:
    try:
        with transaction.atomic():
            return Notification.objects.create(**values), True
    except IntegrityError:
        if not event_identifier:
            raise
        existing = Notification.objects.filter(
            event_identifier=event_identifier,
            channel=NotificationChannels.EMAIL,
        ).first()
        if existing:
            logger.info(
                "Concurrent duplicate skipped for event_identifier=%s.",
                event_identifier,
            )
            return existing, False
        raise


def schedule_notification_dispatch(
    event_code: str,
    request_obj,
    event_identifier: str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> None:
    """
    Registers dispatch to run strictly after the current database transaction commits.
    Prevents emails being sent for transactions that subsequently roll back.
    """
    request_id = request_obj.id if request_obj else None
    transaction.on_commit(
        lambda: _post_commit_dispatch(
            event_code=event_code,
            request_id=request_id,
            event_identifier=event_identifier,
            extra_context=extra_context,
        )
    )


def _post_commit_dispatch(
    event_code: str,
    request_id: int | None,
    event_identifier: str | None,
    extra_context: dict[str, Any] | None,
) -> None:
    """Invoked by transaction.on_commit to load fresh request data and dispatch."""
    from apps.requests.models import Request

    request_obj = None
    if request_id:
        request_obj = (
            Request.objects.select_related("student_id__user_id", "service_id")
            .filter(pk=request_id)
            .first()
        )
        if not request_obj:
            logger.warning("Post-commit dispatch skipped: Request %s not found.", request_id)
            return

    try:
        dispatch_notification(
            event_code=event_code,
            request_obj=request_obj,
            event_identifier=event_identifier,
            extra_context=extra_context,
        )
    except Exception:
        logger.exception(
            "Post-commit notification processing failed for event_code=%s, request_id=%s.",
            event_code,
            request_id,
        )


def retry_notification(notification_id: int, admin_user=None) -> Notification:
    """
    Retry sending an eligible failed notification record.
    Reuses original event identity, respects MAX_RETRIES, and records audit trail.
    """
    with transaction.atomic():
        notification = (
            Notification.objects.select_for_update()
            .filter(pk=notification_id)
            .first()
        )
        if not notification:
            raise ValidationError("Notification record not found.")

        if notification.is_test:
            raise ValidationError("Test notifications must be sent again from the template page.")
        if notification.status != NotificationStatuses.FAILED:
            raise ValidationError(
                f"Only failed notifications can be retried (current status: {notification.status})."
            )
        if notification.retry_count >= MAX_RETRIES:
            raise ValidationError(
                f"Maximum retry limit ({MAX_RETRIES}) reached for this notification."
            )
        if not notification.recipient_email:
            raise ValidationError("Cannot retry: No recipient email address recorded.")

        notification.retry_count += 1
        notification.status = NotificationStatuses.SENDING
        notification.last_attempt_at = timezone.now()
        notification.save(
            update_fields=["retry_count", "status", "last_attempt_at", "updated_at"]
        )

    # Re-dispatch email
    from .template_renderer import html_to_plain_text
    plain_text = html_to_plain_text(notification.message)

    accepted, provider_message_id, error_message, uncertain = send_email(
        to_email=notification.recipient_email,
        subject=notification.subject,
        html_content=notification.message,
        text_content=plain_text,
    )

    now = timezone.now()
    notification.last_attempt_at = now
    notification.provider_message_id = provider_message_id

    if accepted:
        notification.status = NotificationStatuses.SENT
        notification.sent_at = now
        notification.delivery_error = ""
    elif uncertain:
        notification.status = NotificationStatuses.UNCERTAIN
        notification.delivery_error = error_message
    else:
        notification.status = NotificationStatuses.FAILED
        notification.delivery_error = error_message

    notification.save(
        update_fields=[
            "status",
            "sent_at",
            "last_attempt_at",
            "provider_message_id",
            "delivery_error",
            "updated_at",
        ]
    )

    # Record AuditLog
    AuditLog.log(
        request=None,
        action="UPDATE",
        obj=notification,
        object_repr=f"Notification #{notification.id} Retry (Attempt {notification.retry_count})",
        changes={
            "action": "RETRY_EMAIL",
            "retry_count": notification.retry_count,
            "status": notification.status,
            "success": accepted,
        },
        user=admin_user,
    )

    return notification
