from __future__ import annotations
from typing import Any

try:
    from apps.departments.models import ServiceDepartment
    HAS_MODEL = True
except Exception as exc:
    ServiceDepartment = None
    HAS_MODEL = False
    print(f"ServiceDepartment model could not be imported: {exc}")


def run() -> dict[str, Any]:

    """Seed service departments (idempotent)."""

    if not HAS_MODEL:
        return {"created": 0, "updated": 0, "existing": 0, "skipped": True}

    print("\nSeeding service departments...\n")

    departments = [
        {"code": "COE", "name": "Controller of Examinations", "status": "ACTIVE"},
        {"code": "ADM", "name": "Admissions", "status": "ACTIVE"},
        {"code": "REG", "name": "Registration", "status": "ACTIVE"},
        {"code": "FIN", "name": "Finance", "status": "ACTIVE"},
        {"code": "LIB", "name": "Library", "status": "ACTIVE"},
    ]

    created = 0
    updated = 0
    existing = 0

    for dept_data in departments:
        dept, is_created = ServiceDepartment.objects.update_or_create(
            code=dept_data["code"],
            defaults={
                "name": dept_data["name"],
                "status": dept_data.get("status", "ACTIVE"),
            },
        )

        if is_created:
            created += 1
            print(f"  Created department: {dept.code} — {dept.name}")
        else:
            changed = False
            if dept.name != dept_data["name"]:
                changed = True
            if dept.status != dept_data.get("status", "ACTIVE"):
                changed = True
            if changed:
                updated += 1
                print(f"  Updated department: {dept.code} — {dept.name}")
            else:
                existing += 1
                print(f"  Department already exists and is up‑to‑date: {dept.code}")

    print(
        f"\nService department seeding completed. "
        f"Created: {created}, Updated: {updated}, Existing: {existing}"
    )

    return {
        "created": created,
        "updated": updated,
        "existing": existing,
        "skipped": False,
    }