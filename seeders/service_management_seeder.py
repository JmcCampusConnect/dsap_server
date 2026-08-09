from __future__ import annotations
from typing import Any

try:
    from apps.departments.models import ServiceDepartment
    from apps.services.models import Service
    HAS_MODELS = True
except Exception as exc:
    ServiceDepartment = None
    Service = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


# ── Seed data ────────────────────────────────────────────────────────────────

DEPARTMENTS = [
    {"code": "COE",  "name": "Controller of Examinations"},
    {"code": "HOST", "name": "Hostel Administration"},
    {"code": "LIB",  "name": "Library"},
    {"code": "FIN",  "name": "Finance"},
    {"code": "ACAD", "name": "Academic Section"},
]

SERVICES = [
    {
        "code": "COE-001",
        "name": "Transcript Request",
        "dept_code": "COE",
        "base_fee": 500,
        "sla_days": 7,
    },
    {
        "code": "COE-002",
        "name": "Bonafide Certificate",
        "dept_code": "COE",
        "base_fee": 150,
        "sla_days": 3,
    },
    {
        "code": "LIB-001",
        "name": "Library Services",
        "dept_code": "LIB",
        "base_fee": 0,
        "sla_days": 2,
    },
    {
        "code": "HOST-001",
        "name": "Hostel Services",
        "dept_code": "HOST",
        "base_fee": 100,
        "sla_days": 5,
    },
    {
        "code": "COE-003",
        "name": "Name / DOB Correction",
        "dept_code": "COE",
        "base_fee": 250,
        "sla_days": 5,
    },
]


def run() -> dict[str, Any]:
    """Seed service departments and services (idempotent via get_or_create)."""

    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding service departments...\n")

    dept_created = 0
    dept_existing = 0
    dept_map: dict[str, Any] = {}

    for dept_data in DEPARTMENTS:
        dept, created = ServiceDepartment.objects.get_or_create(
            code=dept_data["code"],
            defaults={
                "name": dept_data["name"],
                "status": "ACTIVE",
            },
        )
        dept_map[dept_data["code"]] = dept
        if created:
            dept_created += 1
            print(f"  Created department: {dept.code} — {dept.name}")
        else:
            dept_existing += 1
            print(f"  Department already exists: {dept.code}")

    print(f"\nDepartments — Created: {dept_created}, Existing: {dept_existing}")
    print("\nSeeding services...\n")

    svc_created = 0
    svc_existing = 0

    for svc_data in SERVICES:
        dept = dept_map.get(svc_data["dept_code"])
        if not dept:
            print(f"  Skipped {svc_data['code']}: department {svc_data['dept_code']} not found")
            continue

        _, created = Service.objects.get_or_create(
            code=svc_data["code"],
            defaults={
                "name": svc_data["name"],
                "service_department_id": dept,
                "base_fee": svc_data["base_fee"],
                "sla_days": svc_data["sla_days"],
                "status": "ACTIVE",
            },
        )
        if created:
            svc_created += 1
            print(f"  Created service: {svc_data['code']} — {svc_data['name']}")
        else:
            svc_existing += 1
            print(f"  Service already exists: {svc_data['code']}")

    total_created = dept_created + svc_created
    total_existing = dept_existing + svc_existing

    print(
        f"\nService management seeding completed. "
        f"Created: {total_created}, Existing: {total_existing}"
    )

    return {
        "created": total_created,
        "existing": total_existing,
        "skipped": False,
    }
