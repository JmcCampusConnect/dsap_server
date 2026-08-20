from __future__ import annotations
from typing import Any

try:
    from apps.departments.models import ServiceDepartment
    from apps.services.models import Service, ServiceField, ServiceDocument
    from apps.workflow.models import WorkflowStep
    from apps.accounts.models import Role  # adjust import if needed
    HAS_MODELS = True
except Exception as exc:
    ServiceDepartment = None
    Service = None
    ServiceField = None
    ServiceDocument = None
    WorkflowStep = None
    Role = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")

# ─── Helper to get role by name ──────────────────────────────
def get_role(name):
    try:
        return Role.objects.get(name=name)
    except Role.DoesNotExist:
        print(f"  Role '{name}' not found – skipping workflow steps for this service.")
        return None

# ─── 10 dummy services with fields, documents, and workflow steps ──
SERVICES = [
    {
        "code": "COE-001",
        "name": "Name / DOB Correction",
        "dept_code": "COE",
        "base_fee": 250.00,
        "sla_days": 5,
        "description": "Request for correction of name or date of birth in official records.",
        "fields": [
            {"field_label": "Current Name", "field_type": "TEXT", "is_required": True, "display_order": 1},
            {"field_label": "New Name", "field_type": "TEXT", "is_required": False, "display_order": 2},
            {"field_label": "Reason", "field_type": "TEXTAREA", "is_required": True, "display_order": 3},
        ],
        "documents": [
            {"document_name": "Application Form", "is_mandatory": True},
            {"document_name": "ID Proof", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Request", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Verify Documents", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Approval", "action_type": "APPROVE", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 4, "step_name": "Complete", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "COE-002",
        "name": "Duplicate Degree Certificate",
        "dept_code": "COE",
        "base_fee": 500.00,
        "sla_days": 10,
        "description": "Request for a duplicate copy of the degree certificate.",
        "fields": [
            {"field_label": "Degree", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["B.Sc", "M.Sc", "B.A", "M.A"]},
            {"field_label": "Year of Passing", "field_type": "NUMBER", "is_required": True, "display_order": 2},
        ],
        "documents": [
            {"document_name": "Police Report", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Request", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Verify", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Approve", "action_type": "APPROVE", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 4, "step_name": "Issue Certificate", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "COE-003",
        "name": "Transcript Request",
        "dept_code": "COE",
        "base_fee": 300.00,
        "sla_days": 7,
        "description": "Request for official academic transcript.",
        "fields": [
            {"field_label": "Number of Copies", "field_type": "NUMBER", "is_required": True, "display_order": 1},
            {"field_label": "Purpose", "field_type": "DROPDOWN", "is_required": True, "display_order": 2, "options_json": ["Job", "Higher Study", "Personal"]},
        ],
        "documents": [
            {"document_name": "Payment Receipt", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Verify Payment", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Prepare Transcript", "action_type": "PROCESS", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 4, "step_name": "Dispatch", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "ADM-001",
        "name": "Admission Inquiry",
        "dept_code": "ADM",
        "base_fee": 0.00,
        "sla_days": 2,
        "description": "General inquiries about admission process and eligibility.",
        "fields": [
            {"field_label": "Program", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["UG", "PG"]},
            {"field_label": "Query", "field_type": "TEXTAREA", "is_required": True, "display_order": 2},
        ],
        "documents": [],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Inquiry", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Assign to Counselor", "action_type": "ASSIGN", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Respond", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "ADM-002",
        "name": "Application Status Check",
        "dept_code": "ADM",
        "base_fee": 0.00,
        "sla_days": 1,
        "description": "Check the current status of your admission application.",
        "fields": [
            {"field_label": "Application ID", "field_type": "TEXT", "is_required": True, "display_order": 1},
        ],
        "documents": [],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Query", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Retrieve Status", "action_type": "PROCESS", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Reply", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "REG-001",
        "name": "Course Registration",
        "dept_code": "REG",
        "base_fee": 100.00,
        "sla_days": 3,
        "description": "Register for courses for the upcoming semester.",
        "fields": [
            {"field_label": "Semester", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["Fall", "Spring", "Summer"]},
            {"field_label": "Course List", "field_type": "TEXTAREA", "is_required": True, "display_order": 2},
        ],
        "documents": [
            {"document_name": "Advisor Approval", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Registration", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Advisor Review", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Registration Confirmation", "action_type": "APPROVE", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 4, "step_name": "Complete", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "REG-002",
        "name": "Add/Drop Course",
        "dept_code": "REG",
        "base_fee": 50.00,
        "sla_days": 2,
        "description": "Request to add or drop a course after registration.",
        "fields": [
            {"field_label": "Course to Add", "field_type": "TEXT", "is_required": False, "display_order": 1},
            {"field_label": "Course to Drop", "field_type": "TEXT", "is_required": False, "display_order": 2},
            {"field_label": "Reason", "field_type": "TEXTAREA", "is_required": True, "display_order": 3},
        ],
        "documents": [],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Request", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Advisor Review", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Update Schedule", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "FIN-001",
        "name": "Fee Payment Confirmation",
        "dept_code": "FIN",
        "base_fee": 0.00,
        "sla_days": 1,
        "description": "Confirm payment of tuition or other fees.",
        "fields": [
            {"field_label": "Payment Method", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["Bank Transfer", "Credit Card", "Cash"]},
            {"field_label": "Transaction ID", "field_type": "TEXT", "is_required": True, "display_order": 2},
        ],
        "documents": [
            {"document_name": "Payment Receipt", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Confirmation", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Verify Payment", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Update Ledger", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "FIN-002",
        "name": "Scholarship Application",
        "dept_code": "FIN",
        "base_fee": 0.00,
        "sla_days": 14,
        "description": "Apply for merit-based or need-based scholarships.",
        "fields": [
            {"field_label": "Scholarship Type", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["Merit", "Need", "Sports"]},
            {"field_label": "CGPA", "field_type": "DECIMAL", "is_required": True, "display_order": 2},
            {"field_label": "Family Income", "field_type": "NUMBER", "is_required": False, "display_order": 3},
        ],
        "documents": [
            {"document_name": "Income Certificate", "is_mandatory": False},
            {"document_name": "Recommendation Letter", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Apply", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Review Documents", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Scrutiny", "action_type": "PROCESS", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 4, "step_name": "Final Approval", "action_type": "APPROVE", "responsible_role": "SYSTEM_ADMIN"},
            {"step_order": 5, "step_name": "Disburse", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
    {
        "code": "LIB-001",
        "name": "Library Membership",
        "dept_code": "LIB",
        "base_fee": 200.00,
        "sla_days": 3,
        "description": "Apply for library membership and borrowing privileges.",
        "fields": [
            {"field_label": "Membership Type", "field_type": "DROPDOWN", "is_required": True, "display_order": 1, "options_json": ["Student", "Faculty", "Staff"]},
        ],
        "documents": [
            {"document_name": "ID Card Copy", "is_mandatory": True},
            {"document_name": "Passport Photo", "is_mandatory": True},
        ],
        "workflow_steps": [
            {"step_order": 1, "step_name": "Submit Application", "action_type": "SUBMIT", "responsible_role": "STUDENT"},
            {"step_order": 2, "step_name": "Verify ID", "action_type": "VERIFY", "responsible_role": "SERVICE_DEPT_ADMIN"},
            {"step_order": 3, "step_name": "Activate Membership", "action_type": "COMPLETE", "responsible_role": "SERVICE_DEPT_ADMIN"},
        ]
    },
]

def run() -> dict[str, Any]:
    """Seed services, fields, documents, and workflow steps."""
    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding services with fields, documents, and workflow steps...\n")

    dept_codes = {svc["dept_code"] for svc in SERVICES}
    departments = ServiceDepartment.objects.filter(code__in=dept_codes)
    dept_map = {dept.code: dept for dept in departments}

    created = 0
    existing = 0

    for svc_data in SERVICES:
        dept = dept_map.get(svc_data["dept_code"])
        if not dept:
            print(f"  Skipped {svc_data['code']}: department '{svc_data['dept_code']}' not found.")
            continue

        service, is_created = Service.objects.get_or_create(
            code=svc_data["code"],
            defaults={
                "name": svc_data["name"],
                "service_department_id": dept,
                "base_fee": svc_data["base_fee"],
                "sla_days": svc_data["sla_days"],
                "status": "ENABLED",
                "description": svc_data.get("description", ""),
            },
        )

        if is_created:
            created += 1
            print(f"  Created service: {service.code} — {service.name}")

            # ── Fields ──────────────────────────────────────────
            for field_data in svc_data.get("fields", []):
                ServiceField.objects.create(
                    service_id=service,
                    field_label=field_data["field_label"],
                    field_type=field_data["field_type"],
                    is_required=field_data.get("is_required", False),
                    display_order=field_data.get("display_order", 0),
                    options_json=field_data.get("options_json", None),
                )

            # ── Documents ──────────────────────────────────────
            for doc_data in svc_data.get("documents", []):
                ServiceDocument.objects.create(
                    service_id=service,
                    document_name=doc_data["document_name"],
                    is_mandatory=doc_data.get("is_mandatory", True),
                )

            # ── Workflow Steps ─────────────────────────────────
            for step_data in svc_data.get("workflow_steps", []):
                role = get_role(step_data["responsible_role"])
                if role:
                    WorkflowStep.objects.create(
                        service_id=service,
                        step_order=step_data["step_order"],
                        step_name=step_data["step_name"],
                        responsible_role_id=role,
                        action_type=step_data["action_type"],
                    )
                else:
                    print(f"    Skipped workflow step '{step_data['step_name']}' – role not found.")

        else:
            existing += 1
            print(f"  Service already exists: {service.code}")

    print(f"\nSeeding completed. Created: {created}, Existing: {existing}")
    return {"created": created, "existing": existing, "skipped": False}