"""
Workflow constants and system-wide choices for DASP.
Single Source of Truth for action types and workflow allowed actions.
"""

class ActionTypes:
    REVIEW = "REVIEW"
    PROCESSING = "PROCESSING"
    VERIFICATION = "VERIFICATION"
    NOTIFICATION = "NOTIFICATION"

    @classmethod
    def all(cls):
        return [
            cls.REVIEW,
            cls.PROCESSING,
            cls.VERIFICATION,
            cls.NOTIFICATION,
        ]


ACTION_TYPE_CHOICES = [
    (ActionTypes.REVIEW, "Review"),
    (ActionTypes.PROCESSING, "Processing"),
    (ActionTypes.VERIFICATION, "Verification"),
    (ActionTypes.NOTIFICATION, "Notification"),
]


class AllowedActions:
    REJECT = "REJECT"
    RETURN = "RETURN"
    FORWARD = "FORWARD"
    COMPLETE = "COMPLETE"
    ISSUE = "ISSUE"

    @classmethod
    def all(cls):
        return [
            cls.REJECT,
            cls.RETURN,
            cls.FORWARD,
            cls.COMPLETE,
            cls.ISSUE,
        ]


ALLOWED_ACTION_CHOICES = [
    (AllowedActions.REJECT, "Reject"),
    (AllowedActions.RETURN, "Return for Revision"),
    (AllowedActions.FORWARD, "Forward to Next Step"),
    (AllowedActions.COMPLETE, "Mark as Completed"),
    (AllowedActions.ISSUE, "Issue"),
]


def configure_role_action(role_name, actions, step_name=None, step_order=None):
    """Keep valid actions and enforce the fixed completion and issuance stages."""
    valid_actions = []
    for action in actions or []:
        if action in AllowedActions.all() and action not in valid_actions:
            valid_actions.append(action)

    if step_order == 4:
        return [AllowedActions.ISSUE]
    valid_actions = [action for action in valid_actions if action != AllowedActions.ISSUE]

    required_action = (
        AllowedActions.COMPLETE
        if step_order == 3 or step_name == "Service Completion"
        else AllowedActions.FORWARD if role_name == "SERVICE_DEPT_STAFF" else None
    )
    if required_action and required_action not in valid_actions:
        valid_actions.append(required_action)
    return valid_actions


class RequestStatuses:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    COMPLETED = "COMPLETED"
    ISSUED = "ISSUED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


class NotificationEventCodes:
    REQ_SUBMITTED = "REQ_SUBMITTED"
    REQ_UNDER_VERIFICATION = "REQ_UNDER_VERIFICATION"
    REQ_COMPLETED = "REQ_COMPLETED"
    REQ_ISSUED = "REQ_ISSUED"
    REQ_RETURNED = "REQ_RETURNED"
    REQ_REJECTED = "REQ_REJECTED"
    REQ_FORWARDED = "REQ_FORWARDED"

    # Map action -> event_code for automatic template lookup
    ACTION_EVENT_MAP = {
        AllowedActions.FORWARD: "REQ_UNDER_VERIFICATION",
        AllowedActions.RETURN: "REQ_RETURNED",
        AllowedActions.REJECT: "REQ_REJECTED",
        AllowedActions.COMPLETE: "REQ_COMPLETED",
        AllowedActions.ISSUE: "REQ_ISSUED",
    }
