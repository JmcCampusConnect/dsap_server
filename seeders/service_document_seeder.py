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
    # 1. CIA Reappear - No documents required
    "COE-001": [],
    
    # 2. Transcript Certificate
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
    ],
    
    # 3. Statement of Marks – All Semesters - No documents required
    "COE-003": [],
    
    # 4. Pass Certificate - No documents required
    "COE-004": [],
    
    # 5. Name Correction MS
    "COE-005": [
        {
            "document_name": "Copy of 10th Mark Statement (Proof of Name/DOB)",
            "is_mandatory": True,
        },
        {
            "document_name": "Copy of 12th Mark Statement",
            "is_mandatory": False,
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

            print(f"  Configured {len(docs)} document checklist(s) for {service.code} ({service.name})")

    print(f"\nServiceDocument seeding completed. Total documents configured: {total_created}")
    return {"created": total_created, "existing": 0, "skipped": False}
