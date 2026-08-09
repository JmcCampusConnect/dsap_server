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


SERVICES = [
    {
        "code": "COE-001",
        "name": "Name / DOB Correction",
        "dept_code": "COE",
        "base_fee": 250,
        "sla_days": 5,
    },
]


def run() -> dict[str, Any]:

    """Seed services using existing service departments."""

    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding services...\n")

    dept_codes = {svc["dept_code"] for svc in SERVICES}
    departments = ServiceDepartment.objects.filter(code__in=dept_codes)
    dept_map = {dept.code: dept for dept in departments}

    created = 0
    existing = 0

    for svc_data in SERVICES:
        dept = dept_map.get(svc_data["dept_code"])
        if not dept:
            print(
                f"  Skipped {svc_data['code']}: department '{svc_data['dept_code']}' not found. "
                "Please run service_department_seeder first."
            )
            continue

        service, is_created = Service.objects.get_or_create(
            code=svc_data["code"],
            defaults={
                "name": svc_data["name"],
                "service_department_id": dept,
                "base_fee": svc_data["base_fee"],
                "sla_days": svc_data["sla_days"],
                "status": "ACTIVE",
            },
        )

        if is_created:
            created += 1
            print(f"  Created service: {service.code} — {service.name}")
        else:
            existing += 1
            print(f"  Service already exists: {service.code}")

    print(
        f"\nService seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
    }