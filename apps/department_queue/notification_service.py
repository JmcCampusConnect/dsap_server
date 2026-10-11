"""
Department Queue — Notification Service
Generates student notifications for workflow transitions using existing
NotificationTemplate records. Follows the same creation pattern as the
request_seeder so behaviour is consistent across the system.
"""
import logging

from apps.notifications.models import Notification, NotificationTemplate
from apps.workflow.constants import NotificationEventCodes

logger = logging.getLogger(__name__)


def send_workflow_notification(request_obj, action: str) -> None:
    """
    Look up the NotificationTemplate for *action* and create a Notification
    record for the student who owns *request_obj*.

    Missing templates are logged as a warning but never raise — a failed
    notification must never roll back a completed workflow transition.
    """
    event_code = NotificationEventCodes.ACTION_EVENT_MAP.get(action)
    if not event_code:
        return  # Some actions (e.g. HOLD) intentionally have no notification

    student_user = None
    try:
        student_user = request_obj.student_id.user_id
    except Exception:
        logger.warning(
            "send_workflow_notification: could not resolve student user for request %s",
            request_obj.id,
        )
        return

    templates = list(
        NotificationTemplate.objects.filter(event_code=event_code)
    )

    if not templates:
        logger.warning(
            "send_workflow_notification: no NotificationTemplate found for event_code=%s; "
            "skipping notification for request %s.",
            event_code,
            request_obj.id,
        )
        return

    for template in templates:
        try:
            Notification.objects.create(
                request_id=request_obj,
                user_id=student_user,
                channel=template.channel,
                template_id=template,
                status="QUEUED",
            )
        except Exception:
            logger.exception(
                "send_workflow_notification: failed to create notification "
                "for request %s, event_code=%s, channel=%s",
                request_obj.id,
                event_code,
                template.channel,
            )
