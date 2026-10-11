"""
Workflow constants and system-wide choices for DASP.
Single Source of Truth for action types and workflow allowed actions.
"""

class ActionTypes:
    APPROVAL = "APPROVAL"
    REVIEW = "REVIEW"
    PROCESSING = "PROCESSING"
    VERIFICATION = "VERIFICATION"
    NOTIFICATION = "NOTIFICATION"

    @classmethod
    def all(cls):
        return [
            cls.APPROVAL,
            cls.REVIEW,
            cls.PROCESSING,
            cls.VERIFICATION,
            cls.NOTIFICATION,
        ]


ACTION_TYPE_CHOICES = [
    (ActionTypes.APPROVAL, "Approval"),
    (ActionTypes.REVIEW, "Review"),
    (ActionTypes.PROCESSING, "Processing"),
    (ActionTypes.VERIFICATION, "Verification"),
    (ActionTypes.NOTIFICATION, "Notification"),
]


class AllowedActions:
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETURN = "RETURN"
    FORWARD = "FORWARD"
    HOLD = "HOLD"
    COMPLETE = "COMPLETE"

    @classmethod
    def all(cls):
        return [
            cls.APPROVE,
            cls.REJECT,
            cls.RETURN,
            cls.FORWARD,
            cls.HOLD,
            cls.COMPLETE,
        ]


ALLOWED_ACTION_CHOICES = [
    (AllowedActions.APPROVE, "Approve"),
    (AllowedActions.REJECT, "Reject"),
    (AllowedActions.RETURN, "Return for Revision"),
    (AllowedActions.FORWARD, "Forward to Next Step"),
    (AllowedActions.HOLD, "Put on Hold"),
    (AllowedActions.COMPLETE, "Mark as Completed"),
]


class RequestStatuses:
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


class NotificationEventCodes:
    REQ_SUBMITTED = "REQ_SUBMITTED"
    REQ_UNDER_VERIFICATION = "REQ_UNDER_VERIFICATION"
    REQ_APPROVED = "REQ_APPROVED"
    REQ_COMPLETED = "REQ_COMPLETED"
    REQ_RETURNED = "REQ_RETURNED"
    REQ_REJECTED = "REQ_REJECTED"
    REQ_FORWARDED = "REQ_FORWARDED"

    # Map action -> event_code for automatic template lookup
    ACTION_EVENT_MAP = {
        AllowedActions.FORWARD: "REQ_UNDER_VERIFICATION",
        AllowedActions.RETURN: "REQ_RETURNED",
        AllowedActions.APPROVE: "REQ_APPROVED",
        AllowedActions.REJECT: "REQ_REJECTED",
        AllowedActions.COMPLETE: "REQ_COMPLETED",
    }
