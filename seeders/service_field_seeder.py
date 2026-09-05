from __future__ import annotations
from typing import Any
from django.db import transaction

try:
    from apps.services.models import Service, ServiceField
    HAS_MODELS = True
except Exception as exc:
    Service = None
    ServiceField = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


def seed_cia_reappear_fields(service: Service) -> int:
    """Fields for COE-001: CIA Reappear."""
    ServiceField.objects.filter(service_id=service).delete()
    count = 0

    # 1. Semester
    ServiceField.objects.create(
        service_id=service,
        field_label="Semester",
        field_type="DROPDOWN",
        is_required=True,
        display_order=1,
        options_json=["Semester 1", "Semester 2", "Semester 3", "Semester 4", "Semester 5", "Semester 6"],
    )
    count += 1

    # 2. Academic Year / Batch
    ServiceField.objects.create(
        service_id=service,
        field_label="Academic Year / Batch",
        field_type="TEXT",
        is_required=True,
        display_order=2,
    )
    count += 1

    # 3. Number of Courses
    num_courses = ServiceField.objects.create(
        service_id=service,
        field_label="Number of Courses for CIA Reappear",
        field_type="DROPDOWN",
        is_required=True,
        display_order=3,
        options_json=["1", "2", "3"],
    )
    count += 1

    # Course 1 (Mandatory)
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 1 - Course Code",
        field_type="TEXT",
        is_required=True,
        display_order=4,
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 1 - Course Title",
        field_type="TEXT",
        is_required=True,
        display_order=5,
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 1 - Name of the Course Teacher",
        field_type="TEXT",
        is_required=True,
        display_order=6,
    )
    count += 3

    # Course 2 (Visible if Number of Courses is 2 or 3)
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 2 - Course Code",
        field_type="TEXT",
        is_required=False,
        display_order=7,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "in",
            "value": ["2", "3"],
        },
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 2 - Course Title",
        field_type="TEXT",
        is_required=False,
        display_order=8,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "in",
            "value": ["2", "3"],
        },
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 2 - Name of the Course Teacher",
        field_type="TEXT",
        is_required=False,
        display_order=9,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "in",
            "value": ["2", "3"],
        },
    )
    count += 3

    # Course 3 (Visible if Number of Courses is 3)
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 3 - Course Code",
        field_type="TEXT",
        is_required=False,
        display_order=10,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "equals",
            "value": "3",
        },
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 3 - Course Title",
        field_type="TEXT",
        is_required=False,
        display_order=11,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "equals",
            "value": "3",
        },
    )
    ServiceField.objects.create(
        service_id=service,
        field_label="Course 3 - Name of the Course Teacher",
        field_type="TEXT",
        is_required=False,
        display_order=12,
        conditional_logic={
            "depends_on_field_id": num_courses.id,
            "operator": "equals",
            "value": "3",
        },
    )
    count += 3

    # 13. Reason
    ServiceField.objects.create(
        service_id=service,
        field_label="Reason for CIA Reappear",
        field_type="TEXT",
        is_required=False,
        display_order=13,
    )
    count += 1

    return count


def seed_transcript_fields(service: Service) -> int:
    """Fields for COE-002: Transcript Certificate."""
    ServiceField.objects.filter(service_id=service).delete()
    count = 0

    # 1. Purpose of Transcript
    purpose_field = ServiceField.objects.create(
        service_id=service,
        field_label="Purpose of Transcript",
        field_type="DROPDOWN",
        is_required=True,
        display_order=1,
        options_json=[
            "Higher Studies Abroad",
            "Job / Employment",
            "WES / Credential Evaluation",
            "Higher Studies in India",
            "Other Purposes",
        ],
    )
    count += 1

    # 2. Number of Sets / Copies
    ServiceField.objects.create(
        service_id=service,
        field_label="Number of Sets / Copies Required",
        field_type="DROPDOWN",
        is_required=True,
        display_order=2,
        options_json=["1", "2", "3", "4", "5"],
    )
    count += 1

    # 3. Delivery Mode
    delivery_field = ServiceField.objects.create(
        service_id=service,
        field_label="Delivery Mode",
        field_type="RADIO",
        is_required=True,
        display_order=3,
        options_json=["In-Person Collection", "Postal / Courier Delivery"],
    )
    count += 1

    # 4. Postal Address (Conditional on Courier)
    ServiceField.objects.create(
        service_id=service,
        field_label="Postal Address with PIN (if courier requested)",
        field_type="TEXT",
        is_required=False,
        display_order=4,
        conditional_logic={
            "depends_on_field_id": delivery_field.id,
            "operator": "equals",
            "value": "Postal / Courier Delivery",
        },
    )
    count += 1

    # 5. WES Ref Number (Conditional on WES)
    ServiceField.objects.create(
        service_id=service,
        field_label="WES Reference Number (if applicable)",
        field_type="TEXT",
        is_required=False,
        display_order=5,
        conditional_logic={
            "depends_on_field_id": purpose_field.id,
            "operator": "equals",
            "value": "WES / Credential Evaluation",
        },
    )
    count += 1

    # 6. Special Instructions
    ServiceField.objects.create(
        service_id=service,
        field_label="Special Instructions / Remarks",
        field_type="TEXT",
        is_required=False,
        display_order=6,
    )
    count += 1

    return count


def seed_statement_of_marks_fields(service: Service) -> int:
    """Fields for COE-003: Statement of Marks – All Semesters."""
    ServiceField.objects.filter(service_id=service).delete()
    count = 0

    # 1. Programme Type
    ServiceField.objects.create(
        service_id=service,
        field_label="Programme Type",
        field_type="DROPDOWN",
        is_required=True,
        display_order=1,
        options_json=["Undergraduate (UG)", "Postgraduate (PG)"],
    )
    count += 1

    # 2. Semester Range
    ServiceField.objects.create(
        service_id=service,
        field_label="Semester Range Required",
        field_type="DROPDOWN",
        is_required=True,
        display_order=2,
        options_json=["All Semesters (Comprehensive)", "Semester 1 to 4", "Semester 1 to 6"],
    )
    count += 1

    # 3. Month & Year of Last Exam
    ServiceField.objects.create(
        service_id=service,
        field_label="Month and Year of Last Examination",
        field_type="TEXT",
        is_required=True,
        display_order=3,
    )
    count += 1

    # 4. Purpose
    ServiceField.objects.create(
        service_id=service,
        field_label="Purpose of Request",
        field_type="DROPDOWN",
        is_required=True,
        display_order=4,
        options_json=["Higher Studies", "Job Application", "Visa Application", "Personal Record", "Other"],
    )
    count += 1

    # 5. Delivery Mode
    delivery_field = ServiceField.objects.create(
        service_id=service,
        field_label="Delivery Mode",
        field_type="RADIO",
        is_required=True,
        display_order=5,
        options_json=["In-Person Collection", "Postal Dispatch"],
    )
    count += 1

    # 6. Postal Address (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Postal Address with PIN (if postal dispatch)",
        field_type="TEXT",
        is_required=False,
        display_order=6,
        conditional_logic={
            "depends_on_field_id": delivery_field.id,
            "operator": "equals",
            "value": "Postal Dispatch",
        },
    )
    count += 1

    # 7. Remarks
    ServiceField.objects.create(
        service_id=service,
        field_label="Remarks / Additional Notes",
        field_type="TEXT",
        is_required=False,
        display_order=7,
    )
    count += 1

    return count


def seed_pass_certificate_fields(service: Service) -> int:
    """Fields for COE-004: Pass Certificate."""
    ServiceField.objects.filter(service_id=service).delete()
    count = 0

    # 1. Month and Year of Passing
    ServiceField.objects.create(
        service_id=service,
        field_label="Month and Year of Passing",
        field_type="TEXT",
        is_required=True,
        display_order=1,
    )
    count += 1

    # 2. Reason for Request
    reason_field = ServiceField.objects.create(
        service_id=service,
        field_label="Reason for Request",
        field_type="DROPDOWN",
        is_required=True,
        display_order=2,
        options_json=["Higher Studies", "Job Application", "Others"],
    )
    count += 1

    # 3. Specify Reason (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Specify Reason (if Others selected)",
        field_type="TEXT",
        is_required=False,
        display_order=3,
        conditional_logic={
            "depends_on_field_id": reason_field.id,
            "operator": "equals",
            "value": "Others",
        },
    )
    count += 1

    # 4. No Dues Clearance Declaration
    ServiceField.objects.create(
        service_id=service,
        field_label="No Dues Clearance Declaration",
        field_type="CHECKBOX",
        is_required=True,
        display_order=4,
        options_json=["I confirm all academic requirements and dues are cleared"],
    )
    count += 1

    # 5. Delivery Mode
    delivery_field = ServiceField.objects.create(
        service_id=service,
        field_label="Delivery Mode",
        field_type="RADIO",
        is_required=True,
        display_order=5,
        options_json=["Counter Collection", "Postal Delivery"],
    )
    count += 1

    # 6. Postal Address (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Postal Address with PIN (if postal delivery)",
        field_type="TEXT",
        is_required=False,
        display_order=6,
        conditional_logic={
            "depends_on_field_id": delivery_field.id,
            "operator": "equals",
            "value": "Postal Delivery",
        },
    )
    count += 1

    return count


def seed_name_correction_fields(service: Service) -> int:
    """Fields for COE-005: Name Correction MS."""
    ServiceField.objects.filter(service_id=service).delete()
    count = 0

    # 1. Correction Type
    corr_type_field = ServiceField.objects.create(
        service_id=service,
        field_label="Correction Type",
        field_type="DROPDOWN",
        is_required=True,
        display_order=1,
        options_json=["Name Correction", "DOB Correction", "Both Name and DOB"],
    )
    count += 1

    # 2. Correct Name (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Correct Name (as per 10th/12th Certificate)",
        field_type="TEXT",
        is_required=False,
        display_order=2,
        conditional_logic={
            "depends_on_field_id": corr_type_field.id,
            "operator": "in",
            "value": ["Name Correction", "Both Name and DOB"],
        },
    )
    count += 1

    # 3. Correct Date of Birth (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Correct Date of Birth (as per Certificate)",
        field_type="DATE",
        is_required=False,
        display_order=3,
        conditional_logic={
            "depends_on_field_id": corr_type_field.id,
            "operator": "in",
            "value": ["DOB Correction", "Both Name and DOB"],
        },
    )
    count += 1

    # 4. Reprint of Mark Statement Required
    reprint_field = ServiceField.objects.create(
        service_id=service,
        field_label="Reprint of Mark Statement Required",
        field_type="DROPDOWN",
        is_required=True,
        display_order=4,
        options_json=[
            "No Reprint Needed",
            "Individual Semester Mark Statement",
            "Consolidated Mark Statement",
            "Both Individual and Consolidated",
        ],
    )
    count += 1

    # 5. Semester(s) for Reprint (Conditional)
    ServiceField.objects.create(
        service_id=service,
        field_label="Semester(s) for Reprint",
        field_type="CHECKBOX",
        is_required=False,
        display_order=5,
        options_json=[
            "Semester 1",
            "Semester 2",
            "Semester 3",
            "Semester 4",
            "Semester 5",
            "Semester 6",
        ],
        conditional_logic={
            "depends_on_field_id": reprint_field.id,
            "operator": "in",
            "value": ["Individual Semester Mark Statement", "Both Individual and Consolidated"],
        },
    )
    count += 1

    # 6. Remark by Student
    ServiceField.objects.create(
        service_id=service,
        field_label="Remark by the Student",
        field_type="TEXT",
        is_required=False,
        display_order=6,
    )
    count += 1

    return count


def run() -> dict[str, Any]:
    """Seed dynamic fields with conditional logic for all 5 COE services."""
    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding dynamic fields for 5 COE services...\n")

    seeder_map = {
        "COE-001": seed_cia_reappear_fields,
        "COE-002": seed_transcript_fields,
        "COE-003": seed_statement_of_marks_fields,
        "COE-004": seed_pass_certificate_fields,
        "COE-005": seed_name_correction_fields,
    }

    total_created = 0

    with transaction.atomic():
        for code, seeder_fn in seeder_map.items():
            try:
                service = Service.objects.get(code=code)
            except Service.DoesNotExist:
                print(f"  Service '{code}' not found. Skipping field seeding for {code}.")
                continue

            created = seeder_fn(service)
            total_created += created
            print(f"  Configured {created} dynamic fields for {service.code} ({service.name})")

    print(f"\nServiceField seeding completed. Total fields configured: {total_created}")
    return {"created": total_created, "existing": 0, "skipped": False}
