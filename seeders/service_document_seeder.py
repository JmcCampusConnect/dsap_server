from __future__ import annotations
from typing import Any
from django.db import transaction

try:
    from apps.services.models import Service, ServiceDocument
    HAS_MODELS = True
except Exception as exc:
    Service = None
    ServiceDocument = None
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


SERVICE_DOCUMENTS = {
    "COE-001": [
        {
            "document_name": "Previous Semester Mark Statement / CIA Grade Card",
            "is_mandatory": True,
        },
        {
            "document_name": "Course Teacher Recommendation / Attendance Slip",
            "is_mandatory": False,
        },
    ],
    "COE-002": [
        {
            "document_name": "Copy of Consolidated Mark Statement",
            "is_mandatory": True,
        },
        {
            "document_name": "Passport Size Photograph",
            "is_mandatory": True,
        },
        {
            "document_name": "WES / Credential Evaluation Form",
            "is_mandatory": False,
        },
        {
            "document_name": "Government / College ID Proof",
            "is_mandatory": False,
        },
    ],
    "COE-003": [
        {
            "document_name": "Copies of Individual Semester Mark Statements",
            "is_mandatory": True,
        },
        {
            "document_name": "Student ID Card / Govt ID Proof",
            "is_mandatory": True,
        },
    ],
    "COE-004": [
        {
            "document_name": "Final Semester Mark Sheet / Provisional Certificate Copy",
            "is_mandatory": True,
        },
        {
            "document_name": "Student ID Card",
            "is_mandatory": True,
        },
        {
            "document_name": "No Dues Clearance Slip",
            "is_mandatory": False,
        },
    ],
    "COE-005": [
        {
            "document_name": "Copy of 10th Mark Statement (Proof of Name/DOB)",
            "is_mandatory": True,
        },
        {
            "document_name": "Copy of 12th Mark Statement",
            "is_mandatory": False,
        },
        {
            "document_name": "Existing Mark Statement(s) to be Corrected",
            "is_mandatory": True,
        },
    ],
}


def run() -> dict[str, Any]:
    """Seed required and optional documents for the 5 COE services."""
    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding service documents for 5 COE services...\n")

    total_created = 0

    with transaction.atomic():
        for code, docs in SERVICE_DOCUMENTS.items():
            try:
                service = Service.objects.get(code=code)
            except Service.DoesNotExist:
                print(f"  Service '{code}' not found. Skipping document seeding.")
                continue

            # Clear old documents for clean state
            ServiceDocument.objects.filter(service_id=service).delete()

            for doc_info in docs:
                ServiceDocument.objects.create(
                    service_id=service,
                    document_name=doc_info["document_name"],
                    is_mandatory=doc_info["is_mandatory"],
                )
                total_created += 1

            print(f"  Configured {len(docs)} document checklists for {service.code} ({service.name})")

    print(f"\nServiceDocument seeding completed. Total documents configured: {total_created}")
    return {"created": total_created, "existing": 0, "skipped": False}
