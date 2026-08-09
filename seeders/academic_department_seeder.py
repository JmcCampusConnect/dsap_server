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
    """Seed the academic department table with initial sample data (5 records)."""

    if not HAS_MODEL:
        return {"created": 0, "updated": 0, "existing": 0, "skipped": True}

    print("\nSeeding initial academic departments...\n")

    departments = [
        {
            'branch': 'COMPUTER APPLICATIONS',
            'category': 'SCIENCE',
            'code': 'MCA',
            'degree': 'M.C.A.',
            'status': 'ACTIVE',
            'stream': 'Aided',
            'type': 'PG'
        },
        {
            'branch': 'COMPUTER SCIENCE',
            'category': 'SCIENCE',
            'code': 'UCS',
            'degree': 'B.Sc.',
            'status': 'ACTIVE',
            'stream': 'Aided',
            'type': 'UG'
        },
        {
            'branch': 'BUSINESS ADMINISTRATION',
            'category': 'ARTS',
            'code': 'MBA',
            'degree': 'M.B.A.',
            'status': 'ACTIVE',
            'stream': 'SFM',
            'type': 'PG'
        },
        {
            'branch': 'COMPUTER APPLICATIONS',
            'category': 'SCIENCE',
            'code': 'UCA',
            'degree': 'B.C.A.',
            'status': 'ACTIVE',
            'stream': 'SFM',
            'type': 'UG'
        },
        {
            'branch': 'COMMERCE',
            'category': 'ARTS',
            'code': 'UCO',
            'degree': 'B.Com.',
            'status': 'ACTIVE',
            'stream': 'SFW',
            'type': 'UG'
        }
    ]

    created = 0
    existing = 0

    for department_data in departments:
        department, is_created = AcademicDepartment.objects.get_or_create(
            code=department_data["code"],
            stream=department_data["stream"],
            defaults={
                "degree": department_data["degree"],
                "branch": department_data["branch"],
                "type": department_data["type"],
                "category": department_data["category"],
                "status": department_data["status"],
            },
        )

        if is_created:
            created += 1
            print(f"Created department: {department.code} ({department.stream}) - {department.degree} {department.branch}")
        else:
            existing += 1
            print(f"Existing department preserved: {department.code} ({department.stream}) - {department.degree} {department.branch}")

    print(
        f"Academic department seeding completed. "
        f"Created: {created}, Existing: {existing}, Total Initial Seed Data: {len(departments)}"
    )

    return {
        "created": created,
        "existing": existing,
        "total": len(departments),
        "skipped": False,
    }
