from __future__ import annotations
from typing import Any
from django.db import transaction

try:
    from apps.accounts.models import Role
    from apps.services.models import Service
    from apps.workflow.models import WorkflowStep
    from apps.workflow.constants import ActionTypes, AllowedActions
    HAS_MODELS = True
except Exception as exc:
    Role = None
    Service = None
    WorkflowStep = None
    ActionTypes = None
    AllowedActions = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


SERVICE_WORKFLOWS = {
    "COE-001": [
        {
            "step_order": 1,
            "step_name": "Course Teacher Review",
            "responsible_role": "SUBJECT_TEACHING_STAFF",
            "action_type": ActionTypes.REVIEW if HAS_MODELS else "REVIEW",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 2,
            "step_name": "Document & Fee Verification",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.VERIFICATION if HAS_MODELS else "VERIFICATION",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 3,
            "step_name": "COE Admin Final Approval",
            "responsible_role": "SERVICE_DEPT_ADMIN",
            "action_type": ActionTypes.APPROVAL if HAS_MODELS else "APPROVAL",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
            ],
        },
    ],
    "COE-002": [
        {
            "step_order": 1,
            "step_name": "Document & Record Verification",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.VERIFICATION if HAS_MODELS else "VERIFICATION",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 2,
            "step_name": "Transcript Preparation & Sealing",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.PROCESSING if HAS_MODELS else "PROCESSING",
            "allowed_actions": [
                AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 3,
            "step_name": "COE Attestation & Approval",
            "responsible_role": "SERVICE_DEPT_ADMIN",
            "action_type": ActionTypes.APPROVAL if HAS_MODELS else "APPROVAL",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
            ],
        },
    ],
    "COE-003": [
        {
            "step_order": 1,
            "step_name": "Academic Record & Document Verification",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.VERIFICATION if HAS_MODELS else "VERIFICATION",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 2,
            "step_name": "Statement Compilation & Printing",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.PROCESSING if HAS_MODELS else "PROCESSING",
            "allowed_actions": [
                AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 3,
            "step_name": "COE Admin Final Approval",
            "responsible_role": "SERVICE_DEPT_ADMIN",
            "action_type": ActionTypes.APPROVAL if HAS_MODELS else "APPROVAL",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
            ],
        },
    ],
    "COE-004": [
        {
            "step_order": 1,
            "step_name": "Eligibility & Dues Verification",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.VERIFICATION if HAS_MODELS else "VERIFICATION",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 2,
            "step_name": "Pass Certificate Preparation",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.PROCESSING if HAS_MODELS else "PROCESSING",
            "allowed_actions": [
                AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 3,
            "step_name": "COE Admin Approval & Seal",
            "responsible_role": "SERVICE_DEPT_ADMIN",
            "action_type": ActionTypes.APPROVAL if HAS_MODELS else "APPROVAL",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
            ],
        },
    ],
    "COE-005": [
        {
            "step_order": 1,
            "step_name": "Proof Document & Record Verification",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.VERIFICATION if HAS_MODELS else "VERIFICATION",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 2,
            "step_name": "ERP Record Update & Statement Re-issue",
            "responsible_role": "SERVICE_DEPT_STAFF",
            "action_type": ActionTypes.PROCESSING if HAS_MODELS else "PROCESSING",
            "allowed_actions": [
                AllowedActions.FORWARD if HAS_MODELS else "FORWARD",
                AllowedActions.RETURN if HAS_MODELS else "RETURN",
            ],
        },
        {
            "step_order": 3,
            "step_name": "COE Admin Final Approval",
            "responsible_role": "SERVICE_DEPT_ADMIN",
            "action_type": ActionTypes.APPROVAL if HAS_MODELS else "APPROVAL",
            "allowed_actions": [
                AllowedActions.APPROVE if HAS_MODELS else "APPROVE",
                AllowedActions.REJECT if HAS_MODELS else "REJECT",
            ],
        },
    ],
}


def run() -> dict[str, Any]:
    """Seed multi-step workflow configuration for the 5 COE services."""
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
            WorkflowStep.objects.filter(service_id=service).delete()

            for step_data in steps:
                role = roles.get(step_data["responsible_role"])
                if not role:
                    print(f"  Warning: Role '{step_data['responsible_role']}' not found. Skipping step '{step_data['step_name']}'.")
                    continue

                WorkflowStep.objects.create(
                    service_id=service,
                    step_order=step_data["step_order"],
                    step_name=step_data["step_name"],
                    responsible_role_id=role,
                    action_type=step_data["action_type"],
                    allowed_actions=step_data["allowed_actions"],
                )
                total_created += 1

            print(f"  Configured {len(steps)} workflow steps for {service.code} ({service.name})")

    print(f"\nWorkflowStep seeding completed. Total steps configured: {total_created}")
    return {"created": total_created, "existing": 0, "skipped": False}
