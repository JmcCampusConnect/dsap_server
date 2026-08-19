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

    @classmethod
    def all(cls):
        return [
            cls.APPROVE,
            cls.REJECT,
            cls.RETURN,
            cls.FORWARD,
            cls.HOLD,
        ]


ALLOWED_ACTION_CHOICES = [
    (AllowedActions.APPROVE, "Approve"),
    (AllowedActions.REJECT, "Reject"),
    (AllowedActions.RETURN, "Return for Revision"),
    (AllowedActions.FORWARD, "Forward to Next Step"),
    (AllowedActions.HOLD, "Put on Hold"),
]
