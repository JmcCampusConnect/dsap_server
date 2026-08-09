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

    fields = [
        {
            "field_label": "Correct Name",
            "field_type": "TEXT",
            "is_required": True,
            "display_order": 1,
            "options_json": None,
        },
        {
            "field_label": "Correct Date of Birth",
            "field_type": "DATE",
            "is_required": True,
            "display_order": 2,
            "options_json": None,
        },
        {
            "field_label": "Reprint of Mark Statement Requested",
            "field_type": "CHECKBOX",
            "is_required": False,
            "display_order": 3,
            "options_json": [
                "Consolidated",
                "1st Semester",
                "2nd Semester",
                "3rd Semester",
                "4th Semester",
                "5th Semester",
                "6th Semester",
            ],
        },
        {
            "field_label": "Remark by Student",
            "field_type": "TEXTAREA",
            "is_required": False,
            "display_order": 4,
            "options_json": None,
        },
    ]

    with transaction.atomic():
        for field_data in fields:
            obj, created = ServiceField.objects.get_or_create(
                service_id=service,
                field_label=field_data["field_label"],
                defaults={
                    "field_type": field_data["field_type"],
                    "is_required": field_data["is_required"],
                    "display_order": field_data["display_order"],
                    "options_json": field_data["options_json"],
                }
            )
            
            if created:
                result["created"] += 1
            else:
                # Update existing
                obj.field_type = field_data["field_type"]
                obj.is_required = field_data["is_required"]
                obj.display_order = field_data["display_order"]
                obj.options_json = field_data["options_json"]
                obj.save()
                result["existing"] += 1

    return result
