"""
Workflow constants and system-wide choices for DASP.
Single Source of Truth for action types and workflow allowed actions.
"""

class WorkflowStepKinds:
    PAYMENT_VERIFY = "PAYMENT_VERIFY"
    VERIFICATION = "VERIFICATION"
    PROCESSING = "PROCESSING"
    COMPLETION = "COMPLETION"
    ISSUANCE = "ISSUANCE"
    CUSTOM = "CUSTOM"

    @classmethod
    def all(cls):
        return [
            cls.PAYMENT_VERIFY,
            cls.VERIFICATION,
            cls.PROCESSING,
            cls.COMPLETION,
            cls.ISSUANCE,
            cls.CUSTOM,
        ]


class AllowedActions:
    PAYMENT_VERIFY = "PAYMENT_VERIFY"
    CONFIRM_PAYMENT = "CONFIRM_PAYMENT"
    REJECT_PAYMENT = "REJECT_PAYMENT"
    REJECT = "REJECT"
    RETURN = "RETURN"
    FORWARD = "FORWARD"
    COMPLETE = "COMPLETE"
    ISSUE = "ISSUE"

    @classmethod
    def all(cls):
        return [
            cls.CONFIRM_PAYMENT,
            cls.REJECT_PAYMENT,
            cls.REJECT,
            cls.RETURN,
            cls.FORWARD,
            cls.COMPLETE,
            cls.ISSUE,
        ]


ALLOWED_ACTION_CHOICES = [
    (AllowedActions.CONFIRM_PAYMENT, "Confirm Payment"),
    (AllowedActions.REJECT_PAYMENT, "Reject Payment"),
    (AllowedActions.REJECT, "Reject"),
    (AllowedActions.RETURN, "Return for Revision"),
    (AllowedActions.FORWARD, "Forward to Next Step"),
    (AllowedActions.COMPLETE, "Mark as Completed"),
    (AllowedActions.ISSUE, "Issue"),
]


def configure_role_action(
    role_name,
    actions,
    step_name=None,
    step_order=None,
    total_steps=None,
    step_kind=None,
):
    """Keep valid actions and enforce the final stages by their workflow position."""
    valid_actions = []
    for action in actions or []:
        if action in AllowedActions.all() and action not in valid_actions:
            valid_actions.append(action)

    normalized_name = (step_name or "").strip().casefold()
    normalized_kind = (step_kind or "").strip().upper()
    if normalized_kind == WorkflowStepKinds.PAYMENT_VERIFY:
        return [AllowedActions.CONFIRM_PAYMENT, AllowedActions.REJECT_PAYMENT]
    if normalized_kind == WorkflowStepKinds.ISSUANCE or normalized_name == "document issuance & delivery" or (
        total_steps is not None and total_steps >= 4 and step_order == total_steps
    ):
        return [AllowedActions.ISSUE]
    if normalized_kind == WorkflowStepKinds.COMPLETION or normalized_name == "service completion" or (
        total_steps is not None and total_steps >= 4 and step_order == total_steps - 1
    ):
        return [AllowedActions.COMPLETE]
    if normalized_kind == WorkflowStepKinds.VERIFICATION or normalized_name in {
        "document & record verification",
        "document verification",
    }:
        return [
            AllowedActions.REJECT,
            AllowedActions.RETURN,
            AllowedActions.FORWARD,
        ]

    valid_actions = [
        action for action in valid_actions
        if action not in {AllowedActions.COMPLETE, AllowedActions.ISSUE}
    ]
    if role_name == "SERVICE_DEPT_STAFF" and AllowedActions.FORWARD not in valid_actions:
        valid_actions.append(AllowedActions.FORWARD)
    return valid_actions


class RequestStatuses:
    DRAFT = "DRAFT"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_ISSUE = "PAYMENT_ISSUE"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    PROCESSING = "PROCESSING"
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
