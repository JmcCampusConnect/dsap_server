from __future__ import annotations
from typing import Any
from django.contrib.auth.hashers import make_password
from datetime import date

try:
    from apps.accounts.models import Role, User
    from apps.students.models import Student
    from apps.departments.models import AcademicDepartment
    HAS_MODELS = True
except Exception as exc:
    Role = User = Student = AcademicDepartment = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


def run() -> dict[str, Any]:

    """Seed student records for predefined register numbers."""

    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding students...\n")

    students_data = [
        {
            "register_number": "24MCA066",
            "name": "Mohamed Jainul Haneef M I",
            "email": "student066@example.com",
            "dob": date(2000, 4, 1),
            "year_of_admission": "2024",
            "section": "A",
            "stream": "SFM",
            "mobile_number": "9876543213",
            "status": True,
            "department_code": "MCA",
            "department_stream": "SFM"
        },
    ]

    student_role, _ = Role.objects.get_or_create(
        name="STUDENT",
        defaults={"description": "Student"}
    )

    departments = {}
    for data in students_data:
        department_key = (data["department_code"], data["department_stream"])
        if department_key not in departments:
            department = AcademicDepartment.objects.filter(
                code=department_key[0],
                stream=department_key[1],
            ).first()
            if department is None:
                print(
                    f"Error: AcademicDepartment {department_key[0]} "
                    f"({department_key[1]}) not found. Please run "
                    "academic_department_seeder first."
                )
                return {"created": 0, "existing": 0, "skipped": True}
            departments[department_key] = department

    created = 0
    existing = 0
    default_password = make_password("jmc")  

    for data in students_data:
        reg_no = data["register_number"]
        dept = departments[(data["department_code"], data["department_stream"])]

        # 1. Create or get the User
        user, user_created = User.objects.get_or_create(
            username=reg_no,
            defaults={
                "email": data["email"],
                "password_hash": default_password,
                "role_id": student_role,
                "is_active": data["status"],
            },
        )
        if user_created:
            print(f"  Created user: {reg_no}")
        elif user.is_active != data["status"]:
            user.is_active = data["status"]
            user.save(update_fields=["is_active"])

        student, student_created = Student.objects.update_or_create(
            register_number=reg_no,
            defaults={
                "name": data["name"],
                "dob": data["dob"],
                "user_id": user,
                "academic_department_id": dept,
                "year_of_admission": data["year_of_admission"],
                "section": data["section"],
                "stream": data["stream"],
                "mobile_number": data["mobile_number"],
                "status": data["status"],
            },
        )

        if student_created:
            created += 1
            print(f"  Created student: {reg_no} ({data['name']})")
        else:
            existing += 1
            print(f"  Updated demo student: {reg_no}")

    print(
        f"\nStudent seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
    }
