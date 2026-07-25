from __future__ import annotations
from typing import Any

try:
    from apps.departments.models import AcademicDepartment
    HAS_MODEL = True
except Exception as exc:
    AcademicDepartment = None
    HAS_MODEL = False
    print(f"AcademicDepartment model could not be imported: {exc}")

def run() -> dict[str, Any]:
    """Seed the academic department table with default departments."""

    if not HAS_MODEL:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding academic departments...\n")

    departments = [
        {
            "code": "UCA",
            "name": "Bachelor of Computer Applications",
            "degree": "BCA",
            "branch": "Computer Applications",
            "type": "UG",
            "category": "AIDED",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "PCA",
            "name": "Master of Computer Applications",
            "degree": "MCA",
            "branch": "Computer Applications",
            "type": "PG",
            "category": "SFM",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "UCS",
            "name": "Computer Science",
            "degree": "B.Sc",
            "branch": "Computer Science",
            "type": "UG",
            "category": "AIDED",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "UAR",
            "name": "Arabic",
            "degree": "B.A",
            "branch": "Arabic",
            "type": "UG",
            "category": "AIDED",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "UEN",
            "name": "English",
            "degree": "B.A",
            "branch": "English",
            "type": "UG",
            "category": "SFW",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "UTA",
            "name": "Tamil",
            "degree": "B.A",
            "branch": "Tamil",
            "type": "UG",
            "category": "AIDED",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
        {
            "code": "UMA",
            "name": "Mathematics",
            "degree": "B.Sc",
            "branch": "Mathematics",
            "type": "UG",
            "category": "SFM",
            "hod_user_id": None,
            "status": "ACTIVE",
        },
    ]

    created = 0
    existing = 0

    for department_data in departments:

        department, is_created = AcademicDepartment.objects.get_or_create(
            code=department_data["code"],
            defaults={
                "name": department_data["name"],
                "degree": department_data["degree"],
                "branch": department_data["branch"],
                "type": department_data["type"],
                "category": department_data["category"],
                "hod_user_id": department_data["hod_user_id"],
                "status": department_data["status"],
            },
        )

        if is_created:
            created += 1
            print(f"Created department: {department.code} - {department.name}")
        else:
            existing += 1
            print(f"Department already exists: {department.code}")

    print(
        f"Academic department seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
        }