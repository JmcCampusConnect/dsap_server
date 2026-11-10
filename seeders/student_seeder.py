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

    fixtures = [
        ("24MCA066", "2024", "A", "AIDED", True, "MCA", "Aided", date(2002, 2, 6)),
        ("24UCS067", "2024", "A", "SFM", True, "UCS", "SFM", date(2005, 3, 7)),
        ("23PEN068", "2023", "B", "SFW", False, "PEN", "SFW", date(2002, 4, 8)),
        ("24UCO069", "2024", "B", "AIDED", False, "UCO", "Aided", date(2005, 5, 9)),
        ("23PMA070", "2023", "A", "AIDED", True, "PMA", "Aided", date(2001, 6, 10)),
        ("22UAR071", "2022", "C", "SFW", True, "UAR", "SFW", date(2004, 7, 11)),
        ("24PEN072", "2024", "B", "AIDED", True, "PEN", "Aided", date(2002, 8, 12)),
        ("23UBO073", "2023", "C", "AIDED", False, "UBO", "Aided", date(2004, 9, 13)),
        ("22MCA074", "2022", "D", "SFM", True, "MCA", "SFM", date(2000, 10, 14)),
        ("22UCS075", "2022", "A", "SFW", True, "UCS", "SFW", date(2003, 11, 15)),
        ("25MCA076", "2025", "B", "AIDED", True, "MCA", "Aided", date(2003, 1, 16)),
        ("25UAR077", "2025", "C", "AIDED", False, "UAR", "Aided", date(2007, 2, 17)),
        ("25UCO078", "2025", "D", "SFM", False, "UCO", "SFM", date(2007, 3, 18)),
        ("24PEN079", "2024", "C", "SFW", True, "PEN", "SFW", date(2003, 4, 19)),
        ("23UCS080", "2023", "D", "SFM", False, "UCS", "SFM", date(2006, 5, 20)),
        ("22PMA081", "2022", "B", "AIDED", True, "PMA", "Aided", date(2000, 6, 21)),
        ("25UCO082", "2025", "A", "SFW", True, "UCO", "SFW", date(2007, 7, 22)),
        ("24MCA083", "2024", "D", "SFM", False, "MCA", "SFM", date(2002, 8, 23)),
        ("23UCO084", "2023", "B", "AIDED", True, "UCO", "Aided", date(2005, 9, 24)),
        ("25PEN085", "2025", "C", "SFW", False, "PEN", "SFW", date(2003, 10, 25)),
    ]
    students_data = [
        {
            "register_number": register_number,
            "name": f"Demo Student {register_number[-3:]}",
            "email": f"student{register_number[-3:]}@example.com",
            "dob": dob,
            "year_of_admission": year_of_admission,
            "section": section,
            "stream": stream,
            "mobile_number": f"98765{int(register_number[-3:]):05d}",
            "status": is_active,
            "department_code": department_code,
            "department_stream": department_stream,
        }
        for (
            register_number,
            year_of_admission,
            section,
            stream,
            is_active,
            department_code,
            department_stream,
            dob,
        ) in fixtures
    ]

    # Get or create the STUDENT role
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
