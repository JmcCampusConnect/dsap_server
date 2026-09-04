from __future__ import annotations
from typing import Any
from django.db import transaction

try:
    from apps.departments.models import ServiceDepartment
    from apps.services.models import Service
    HAS_MODELS = True
except Exception as exc:
    ServiceDepartment = None
    Service = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


COE_SERVICES = [
    {
        "code": "COE-001",
        "name": "CIA Reappear",
        "dept_code": "COE",
        "base_fee": 150.00,
        "sla_days": 7,
        "description": "Application for appearing in Continuous Internal Assessment (CIA) Reappear Examination for eligible course(s).",
    },
    {
        "code": "COE-002",
        "name": "Transcript Certificate",
        "dept_code": "COE",
        "base_fee": 500.00,
        "sla_days": 7,
        "description": "Official academic transcript certificate issued for higher education, overseas credential evaluation (WES), or employment verification.",
    },
    {
        "code": "COE-003",
        "name": "Statement of Marks – All Semesters",
        "dept_code": "COE",
        "base_fee": 250.00,
        "sla_days": 5,
        "description": "Issuance of comprehensive statement of marks summarizing results secured across all completed semesters.",
    },
    {
        "code": "COE-004",
        "name": "Pass Certificate",
        "dept_code": "COE",
        "base_fee": 200.00,
        "sla_days": 3,
        "description": "Issuance of official Pass Certificate certifying successful completion of all academic requirements and no pending dues.",
    },
    {
        "code": "COE-005",
        "name": "Name Correction MS",
        "dept_code": "COE",
        "base_fee": 300.00,
        "sla_days": 5,
        "description": "Request for correction of Student Name or Date of Birth in official COE examination records and re-issuance of mark statements.",
    },
]


def run() -> dict[str, Any]:
    """Seed the 5 COE services (idempotent)."""
    if not HAS_MODELS:
        return {"created": 0, "updated": 0, "existing": 0, "skipped": True}

    print("\nSeeding 5 COE services...\n")

    coe_dept = ServiceDepartment.objects.filter(code="COE").first()
    if not coe_dept:
        print("  Error: ServiceDepartment 'COE' not found. Please run service_department_seeder first.")
        return {"created": 0, "updated": 0, "existing": 0, "skipped": True}

    created = 0
    updated = 0
    existing = 0

    with transaction.atomic():
        for svc_data in COE_SERVICES:
            service, is_created = Service.objects.update_or_create(
                code=svc_data["code"],
                defaults={
                    "name": svc_data["name"],
                    "service_department_id": coe_dept,
                    "base_fee": svc_data["base_fee"],
                    "sla_days": svc_data["sla_days"],
                    "status": True,
                    "description": svc_data.get("description", ""),
                },
            )

            if is_created:
                created += 1
                print(f"  Created service: {service.code} — {service.name}")
            else:
                updated += 1
                print(f"  Updated service: {service.code} — {service.name}")

    print(f"\nCOE Service seeding completed. Created: {created}, Updated: {updated}")
    return {"created": created, "updated": updated, "existing": existing, "skipped": False}
