from __future__ import annotations
from typing import Any
from django.contrib.auth.hashers import make_password

try:
    from apps.accounts.models import Role, User
    HAS_MODEL = True
except Exception as exc:  
    Role = User = None
    HAS_MODEL = False
    print(f"User models could not be imported: {exc}")


def run() -> dict[str, Any]:

    """Seed default users for all system roles."""

    if not HAS_MODEL:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding users...\n")

    created = 0
    existing = 0
    default_password = make_password("jmc")

    users = [
        {
            "role": "SYSTEM_ADMIN",
            "username": "SYSTEM_ADMIN",
            "email": "sysadmin@example.com",
        },
        {
            "role": "SERVICE_DEPT_ADMIN",
            "username": "COE_ADMIN",
            "email": "coe.admin@example.com",
        },
        {
            "role": "SERVICE_DEPT_STAFF",
            "username": "COE_STAFF",
            "email": "coe.staff1@example.com",
        },
        {
            "role": "SUBJECT_TEACHING_STAFF",
            "username": "JMCMTS0006",
            "email": "prof.saq@example.com",
        },
        {
            "role": "STUDENT",
            "username": "21MCA066",
            "email": "ashraf@example.com",
        },
    ]

    for user_data in users:

        role = Role.objects.filter(name=user_data["role"]).first()

        if role is None:
            print(f"Role '{user_data['role']}' not found. Skipping.")
            continue

        user, is_created = User.objects.get_or_create(
            username=user_data["username"],
            defaults={
                "email": user_data["email"],
                "password_hash": default_password,
                "role_id": role,
                "is_active": True,
            },
        )

        if is_created:
            created += 1
            print(
                f"Created {user_data['role']} user: {user.username}"
            )
        else:
            existing += 1
            print(
                f"{user_data['role']} user already exists: {user.username}"
            )

    print(
        f"User seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
    }