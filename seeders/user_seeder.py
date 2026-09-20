from __future__ import annotations
from typing import Any
from django.contrib.auth.hashers import make_password

try:
    from apps.accounts.models import Role, User
    from apps.departments.models import ServiceDepartment
    HAS_MODEL = True
except Exception as exc:
    Role = User = ServiceDepartment = None
    HAS_MODEL = False
    print(f"User models could not be imported: {exc}")


def run() -> dict[str, Any]:
    """Seed default users for all system roles.

    Service Department scoping requires `service_department_id` to be set on
    SERVICE_DEPT_ADMIN / SERVICE_DEPT_STAFF rows. Two departments are populated
    (COE and LIB) so cross-department isolation can be verified end-to-end.
    """

    if not HAS_MODEL:
        return {"created": 0, "updated": 0, "existing": 0, "skipped": True}

    print("\nSeeding users...\n")

    created = 0
    updated = 0
    existing = 0
    default_password = make_password("jmc")

    users = [
        # ── System-wide admin: never department-scoped ─────────────────
        {
            "role": "SYSTEM_ADMIN",
            "username": "SYSTEM_ADMIN",
            "email": "sysadmin@example.com",
            "service_department_code": None,
        },

        # ── Department A — COE ─────────────────────────────────────────
        {
            "role": "SERVICE_DEPT_ADMIN",
            "username": "COE_ADMIN",
            "email": "coe.admin@example.com",
            "service_department_code": "COE",
        },
        {
            "role": "SERVICE_DEPT_STAFF",
            "username": "COE_STAFF",
            "email": "coe.staff1@example.com",
            "service_department_code": "COE",
        },
        {
            # Second staff row so list filtering and pagination are visible
            # inside a single department.
            "role": "SERVICE_DEPT_STAFF",
            "username": "COE_STAFF_2",
            "email": "coe.staff2@example.com",
            "service_department_code": "COE",
        },

        # ── Department B — LIB (proves cross-department isolation) ─────
        {
            "role": "SERVICE_DEPT_ADMIN",
            "username": "LIB_ADMIN",
            "email": "lib.admin@example.com",
            "service_department_code": "LIB",
        },
        {
            "role": "SERVICE_DEPT_STAFF",
            "username": "LIB_STAFF",
            "email": "lib.staff1@example.com",
            "service_department_code": "LIB",
        },

        # ── Non-dept-scoped roles (unchanged) ──────────────────────────
        {
            "role": "SUBJECT_TEACHING_STAFF",
            "username": "JMCMTS0006",
            "email": "prof.saq@example.com",
            "service_department_code": None,
        },
        {
            "role": "STUDENT",
            "username": "24MCA057",
            "email": "student057@example.com",
            "service_department_code": None,
        },
        {
            "role": "STUDENT",
            "username": "24MCA064",
            "email": "student064@example.com",
            "service_department_code": None,
        },
        {
            "role": "STUDENT",
            "username": "24MCA065",
            "email": "student065@example.com",
            "service_department_code": None,
        },
        {
            "role": "STUDENT",
            "username": "24MCA066",
            "email": "student066@example.com",
            "service_department_code": None,
        },
    ]

    # Cache DB lookups so we resolve each role / department at most once
    # per seeder run.
    role_cache = {}
    dept_cache = {}

    for user_data in users:

        # --- Resolve role --------------------------------------------
        role = role_cache.get(user_data["role"])
        if role is None:
            role = Role.objects.filter(name=user_data["role"]).first()
            if role is None:
                print(
                    f"Role '{user_data['role']}' not found. "
                    f"Skipping user '{user_data['username']}'."
                )
                continue
            role_cache[user_data["role"]] = role

        # --- Resolve service department (when applicable) ------------
        dept_code = user_data.get("service_department_code")
        dept = None
        if dept_code:
            if dept_code not in dept_cache:
                dept_cache[dept_code] = ServiceDepartment.objects.filter(
                    code=dept_code
                ).first()
            dept = dept_cache[dept_code]
            if dept is None:
                # Do not abort — the user is still useful for non-scoped tests.
                # The warning surfaces a runner-order mistake.
                print(
                    f"  WARNING: Service department '{dept_code}' not found. "
                    f"Seeding '{user_data['username']}' without a department."
                )

        user, is_created = User.objects.get_or_create(
            username=user_data["username"],
            defaults={
                "email": user_data["email"],
                "password_hash": default_password,
                "role_id": role,
                "service_department_id": dept,
                "is_active": True,
            },
        )

        if is_created:
            created += 1
            dept_label = f" [dept={dept.code}]" if dept else ""
            print(f"  Created {user_data['role']} user: {user.username}{dept_label}")
            continue

        # --- Backfill: existing rows from before this ticket ---------
        # Re-running the seeder on an old database must pick up the new
        # department assignments without requiring a manual migration.
        current_dept_id = getattr(user, "service_department_id_id", None)
        target_dept_id = dept.id if dept else None

        if current_dept_id != target_dept_id:
            user.service_department_id = dept
            user.save(update_fields=["service_department_id"])
            updated += 1
            dept_label = f"dept={dept.code}" if dept else "dept=None"
            print(f"  Updated {user_data['role']} user: {user.username} -> {dept_label}")
        else:
            existing += 1
            print(f"  {user_data['role']} user already exists and is up-to-date: {user.username}")

    print(
        f"\nUser seeding completed. "
        f"Created: {created}, Updated: {updated}, Existing: {existing}"
    )

    return {
        "created": created,
        "updated": updated,
        "existing": existing,
        "skipped": False,
    }