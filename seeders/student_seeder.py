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
            "register_number": "24MCA057",
            "name": "Abdul Rasak H",
            "email": "student057@example.com",
            "dob": date(2000, 1, 1),
            "batch_year": "2024-2026",
            "section": "A",
            "mobile_number": "9876543210",
        },
        {
            "register_number": "24MCA064",
            "name": "Mohamed Hamdhan J",
            "email": "student064@example.com",
            "dob": date(2000, 2, 1),
            "batch_year": "2024-2026",
            "section": "A",
            "mobile_number": "9876543211",
        },
        {
            "register_number": "24MCA065",
            "name": "Mohamed Hanifa M",
            "email": "student065@example.com",
            "dob": date(2000, 3, 1),
            "batch_year": "2024-2026",
            "section": "A",
            "mobile_number": "9876543212",
        },
        {
            "register_number": "24MCA066",
            "name": "Mohamed Jainul Haneef M I",
            "email": "student066@example.com",
            "dob": date(2000, 4, 1),
            "batch_year": "2024-2026",
            "section": "A",
            "mobile_number": "9876543213",
        },
    ]

    # Get or create the STUDENT role
    student_role, _ = Role.objects.get_or_create(
        name="STUDENT",
        defaults={"description": "Student"}
    )

    # Find an academic department – here we use the MCA (Aided) department
    # If not found, fallback to any MCA department or raise an error.
    try:
        dept = AcademicDepartment.objects.get(code="MCA", stream="Aided")
    except AcademicDepartment.DoesNotExist:
        try:
            dept = AcademicDepartment.objects.get(code="MCA")
        except AcademicDepartment.DoesNotExist:
            print("Error: No AcademicDepartment with code 'MCA' found. Please run academic_department_seeder first.")
            return {"created": 0, "existing": 0, "skipped": True}

    created = 0
    existing = 0
    default_password = make_password("jmc")  

    for data in students_data:
        reg_no = data["register_number"]

        # 1. Create or get the User
        user, user_created = User.objects.get_or_create(
            username=reg_no,
            defaults={
                "email": data["email"],
                "password_hash": default_password,
                "role_id": student_role,
                "is_active": True,
            },
        )
        if user_created:
            print(f"  Created user: {reg_no}")

        # 2. Create or get the Student record
        student, student_created = Student.objects.get_or_create(
            register_number=reg_no,
            defaults={
                "name": data["name"],
                "dob": data["dob"],
                "user_id": user,
                "academic_department_id": dept,
                "batch_year": data["batch_year"],
                "section": data["section"],
                "stream": Student.StreamChoices.SFM,  
                "mobile_number": data["mobile_number"],
                "status": "ACTIVE",
            },
        )

        if student_created:
            created += 1
            print(f"  Created student: {reg_no} ({data['name']})")
        else:
            existing += 1
            print(f"  Student already exists: {reg_no}")

    print(
        f"\nStudent seeding completed. "
        f"Created: {created}, Existing: {existing}"
    )

    return {
        "created": created,
        "existing": existing,
        "skipped": False,
    }