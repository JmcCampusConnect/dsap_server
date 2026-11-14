from __future__ import annotations
from typing import Any
from django.db import transaction

try:
    from apps.accounts.models import Role
    from apps.requests.models import Request
    from apps.services.models import Service
    from apps.workflow.models import WorkflowHistory, WorkflowStep
    from apps.workflow.constants import AllowedActions, WorkflowStepKinds
    HAS_MODELS = True
except Exception as exc:
    Role = None
    Request = None
    Service = None
    WorkflowHistory = None
    WorkflowStep = None
    AllowedActions = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


DEFAULT_WORKFLOW_STEPS = [
    {
        "step_order": 1,
        "step_name": "Document & Record Verification",
        "step_kind": WorkflowStepKinds.VERIFICATION if HAS_MODELS else "VERIFICATION",
        "responsible_role": "SERVICE_DEPT_STAFF",
        "allowed_actions": [
            AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
            AllowedActions.RETURN if HAS_MODELS else "RETURN",
            AllowedActions.REJECT if HAS_MODELS else "REJECT",
        ],
    },
    {
        "step_order": 2,
        "step_name": "Service Processing & Preparation",
        "step_kind": WorkflowStepKinds.PROCESSING if HAS_MODELS else "PROCESSING",
        "responsible_role": "SERVICE_DEPT_STAFF",
        "allowed_actions": [
            AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
            AllowedActions.REJECT if HAS_MODELS else "REJECT",
        ],
    },
    {
        "step_order": 3,
        "step_name": "Service Completion",
        "step_kind": WorkflowStepKinds.COMPLETION if HAS_MODELS else "COMPLETION",
        "responsible_role": "SERVICE_DEPT_STAFF",
        "allowed_actions": [AllowedActions.COMPLETE if HAS_MODELS else "COMPLETE"],
    },
    {
        "step_order": 4,
        "step_name": "Document Issuance & Delivery",
        "step_kind": WorkflowStepKinds.ISSUANCE if HAS_MODELS else "ISSUANCE",
        "responsible_role": "SERVICE_DEPT_STAFF",
        "allowed_actions": [AllowedActions.ISSUE if HAS_MODELS else "ISSUE"],
    },
]

SERVICE_WORKFLOWS = {
    code: DEFAULT_WORKFLOW_STEPS
    for code in ("COE-001", "COE-002", "COE-003", "COE-004", "COE-005")
}


def run() -> dict[str, Any]:
    
    """Seed the workflow for five COE services, prepending payment for paid services."""
    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding workflow steps for 5 COE services...\n")

    roles = {r.name: r for r in Role.objects.all()}
    total_created = 0

    with transaction.atomic():

        for code, steps in SERVICE_WORKFLOWS.items():
            try:
                service = Service.objects.get(code=code)
            except Service.DoesNotExist:
                print(f"  Service '{code}' not found. Skipping workflow seeding.")
                continue

            # Clear existing steps for this service
            if WorkflowHistory is not None:
                WorkflowHistory.objects.filter(step_id__service_id=service).delete()
            if Request is not None:
                Request.objects.filter(current_step_id__service_id=service).update(current_step_id=None)
            WorkflowStep.objects.filter(service_id=service).delete()

            configured_steps = []
            if service.base_fee > 0:
                configured_steps.append({
                    "step_order": 1,
                    "step_name": "Payment Verification",
                    "step_kind": WorkflowStepKinds.PAYMENT_VERIFY,
                    "responsible_role": "SERVICE_DEPT_STAFF",
                    "allowed_actions": [
                        AllowedActions.CONFIRM_PAYMENT,
                        AllowedActions.REJECT_PAYMENT,
                    ],
                })
            payment_step_offset = len(configured_steps)
            configured_steps.extend(
                {
                    **step_data,
                    "step_order": step_data["step_order"] + payment_step_offset,
                }
                for step_data in steps
            )

            for step_data in configured_steps:
                role = roles.get(step_data["responsible_role"])
                if not role:
                    print(f"  Warning: Role '{step_data['responsible_role']}' not found. Skipping step '{step_data['step_name']}'.")
                    continue

                WorkflowStep.objects.create(
                    service_id=service,
                    step_order=step_data["step_order"],
                    step_name=step_data["step_name"],
                    step_kind=step_data["step_kind"],
                    responsible_role_id=role,
                    allowed_actions=step_data["allowed_actions"],
                )
                total_created += 1

            print(f"  Configured {len(configured_steps)} workflow steps for {service.code} ({service.name})")

    print(f"\nWorkflowStep seeding completed. Total steps configured: {total_created}")
    return {"created": total_created, "existing": 0, "skipped": False}
