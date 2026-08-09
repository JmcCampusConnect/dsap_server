from apps.services.models import Service, ServiceField
from django.db import transaction

def run() -> dict:

    result = {"created": 0, "existing": 0, "skipped": False}

    try:
        service = Service.objects.get(code="COE-003")
    except Service.DoesNotExist:
        try:
            service = Service.objects.get(name__icontains="Name / DOB")
        except Service.DoesNotExist:
            print("Target Service 'COE-003' ('Name / DOB Correction') not found. Skipping ServiceField seeder.")
            result["skipped"] = True
            return result

    with transaction.atomic():
        
        # Clear old fields for this service to ensure clean state
        ServiceField.objects.filter(service_id=service).delete()

        # Field 1: Controlling parent field "Correction Type"
        parent_field = ServiceField.objects.create(
            service_id=service,
            field_label="Correction Type",
            field_type="DROPDOWN",
            is_required=True,
            display_order=1,
            options_json=["Name", "DOB", "Both"],
            conditional_logic=None,
        )
        result["created"] += 1

        # Field 2: Dependent Field A "Correct Name (if applicable)"
        ServiceField.objects.create(
            service_id=service,
            field_label="Correct Name (if applicable)",
            field_type="TEXT",
            is_required=False,
            display_order=2,
            options_json=None,
            conditional_logic={
                "depends_on_field_id": parent_field.id,
                "operator": "in",
                "value": ["Name", "Both"],
            },
        )
        result["created"] += 1

        # Field 3: Dependent Field B "Correct Date of Birth (if applicable)"
        ServiceField.objects.create(
            service_id=service,
            field_label="Correct Date of Birth (if applicable)",
            field_type="DATE",
            is_required=False,
            display_order=3,
            options_json=None,
            conditional_logic={
                "depends_on_field_id": parent_field.id,
                "operator": "in",
                "value": ["DOB", "Both"],
            },
        )
        result["created"] += 1

        # Field 4: "Reprint of Mark Statement Requested (if applicable)"
        ServiceField.objects.create(
            service_id=service,
            field_label="Reprint of Mark Statement Requested (if applicable)",
            field_type="CHECKBOX",
            is_required=False,
            display_order=4,
            options_json=[
                "1st Semester",
                "2nd Semester",
                "3rd Semester",
                "4th Semester",
                "5th Semester",
                "6th Semester",
                "Consolidated",
            ],
            conditional_logic=None,
        )
        result["created"] += 1

        # Field 5: "Remark by the Student"
        ServiceField.objects.create(
            service_id=service,
            field_label="Remark by the Student",
            field_type="TEXT",
            is_required=False,
            display_order=5,
            options_json=None,
            conditional_logic=None,
        )
        result["created"] += 1

    return result
