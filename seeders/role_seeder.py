from __future__ import annotations
from typing import Any

try:
    from apps.accounts.models import Role
    HAS_MODEL = True
except Exception as exc:
    Role = None
    HAS_MODEL = False
    print(f"Role model could not be imported: {exc}")


def run() -> dict[str, Any]:

    """Seed the role table with default system roles."""

    if not HAS_MODEL:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding roles...\n")

    roles = [
        {
            "name": "SYSTEM_ADMIN",
            "description": "Full System Administrator",
        },
        {
            "name": "SERVICE_DEPT_ADMIN",
            "description": "Service Department Administrator",
        },
        {
            "name": "SERVICE_DEPT_STAFF",
            "description": "Service Department Staff",
        },
        {
            "name": "SUBJECT_TEACHING_STAFF",
            "description": "Subject Teaching Staff",
        },
        {
            "name": "STUDENT",
            "description": "Student",
        },
    ]

    created = 0
    existing = 0

    for role_data in roles:
        
        role, is_created = Role.objects.get_or_create(
            name=role_data["name"],
            defaults={
                "description": role_data["description"],
            },
        )

        if is_created:
            created += 1
            print(f"Created role: {role.name}")
        else:
            existing += 1
            print(f"Role already exists: {role.name}")

    print(
        f"Role seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
    }