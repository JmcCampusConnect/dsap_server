"""
Department Queue — Notification Service
Bridges department queue workflow actions with the central notification system.
Enforces transaction safety (on_commit), event-specific idempotency,
and accurate status/remarks resolution.
"""

import logging

from apps.notifications.services import schedule_notification_dispatch
from apps.workflow.constants import NotificationEventCodes
from apps.workflow.models import WorkflowHistory

logger = logging.getLogger(__name__)


def send_workflow_notification(
    request_obj,
    action: str,
    history_obj: WorkflowHistory | None = None,
    previous_status: str | None = None,
    remarks: str | None = None,
) -> None:
    """
    Trigger an email notification for a workflow transition.
    - Resolves event code from action.
    - Captures stable event_identifier from WorkflowHistory.
    - Captures previous_status and new_status accurately.
    - Schedules dispatch to execute strictly after transaction commit.
    - Safe against exceptions (never breaks the workflow transition).
    """
    event_code = NotificationEventCodes.ACTION_EVENT_MAP.get(action)
    if not event_code:
        # Action has no corresponding notification event
        return

    try:
        # Resolve or find the corresponding WorkflowHistory record
        if not history_obj and request_obj and getattr(request_obj, "id", None):
            history_obj = (
                WorkflowHistory.objects.filter(request_id=request_obj, action=action)
                .order_by("-id")
                .first()
            )

        event_identifier = f"WF_{history_obj.id}" if history_obj else f"REQ_{request_obj.id}_{action}"
        resolved_remarks = remarks
        if resolved_remarks is None and history_obj:
            resolved_remarks = history_obj.remarks or ""

        extra_context = {
            "previous_status": previous_status or "",
            "new_status": getattr(request_obj, "current_status", ""),
            "remarks": resolved_remarks or "",
        }

        schedule_notification_dispatch(
            event_code=event_code,
            request_obj=request_obj,
            event_identifier=event_identifier,
            extra_context=extra_context,
        )
    except Exception as exc:
        logger.exception(
            "send_workflow_notification: failed to schedule notification for request %s, action %s: %s",
            getattr(request_obj, "id", None),
            action,
            exc,
        )
