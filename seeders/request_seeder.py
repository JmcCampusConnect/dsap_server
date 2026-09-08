from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from django.db import transaction

try:
    from apps.accounts.models import Role, User
    from apps.documents.models import Document
    from apps.notifications.models import Notification, NotificationTemplate
    from apps.requests.models import Request, RequestFieldValue
    from apps.services.models import Service, ServiceDocument, ServiceField
    from apps.students.models import Student
    from apps.workflow.models import WorkflowHistory, WorkflowStep
    HAS_MODELS = True
except Exception as exc:
    HAS_MODELS = False
    print(f"Models could not be imported: {exc}")


def create_dt(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def run() -> dict[str, Any]:
    """Seed comprehensive request, field values, workflow history, documents, and notifications."""
    if not HAS_MODELS:
        return {"created": 0, "existing": 0, "skipped": True}

    print("\nSeeding requests, fields, workflow history, documents, and notifications...\n")

    # 1. Fetch required users and students
    student_66 = Student.objects.filter(register_number="24MCA066").first()
    student_57 = Student.objects.filter(register_number="24MCA057").first()

    if not student_66:
        print("Error: Student '24MCA066' not found. Please run student_seeder first.")
        return {"created": 0, "existing": 0, "skipped": True}

    coe_staff = User.objects.filter(username="COE_STAFF").first() or User.objects.filter(role_id__name="SERVICE_DEPT_STAFF").first()
    coe_admin = User.objects.filter(username="COE_ADMIN").first() or User.objects.filter(role_id__name="SERVICE_DEPT_ADMIN").first()
    teacher_user = User.objects.filter(username="JMCMTS0006").first() or User.objects.filter(role_id__name="SUBJECT_TEACHING_STAFF").first()

    # 2. Fetch services
    services = {s.code: s for s in Service.objects.all()}
    if "COE-001" not in services or "COE-002" not in services:
        print("Error: Required services not found. Please run service_seeder first.")
        return {"created": 0, "existing": 0, "skipped": True}

    # 3. Fetch workflow steps by service
    steps_by_service: dict[str, dict[int, WorkflowStep]] = {}
    for step in WorkflowStep.objects.select_related("service_id").all():
        s_code = step.service_id.code
        if s_code not in steps_by_service:
            steps_by_service[s_code] = {}
        steps_by_service[s_code][step.step_order] = step

    # 4. Ensure notification templates
    template_submitted, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_SUBMITTED",
        channel="EMAIL",
        defaults={"template_body": "Your request {request_number} has been submitted successfully."}
    )
    template_verified, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_UNDER_VERIFICATION",
        channel="EMAIL",
        defaults={"template_body": "Your request {request_number} is under verification."}
    )
    template_approved, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_APPROVED",
        channel="EMAIL",
        defaults={"template_body": "Your request {request_number} has been approved."}
    )
    template_completed, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_COMPLETED",
        channel="EMAIL",
        defaults={"template_body": "Your certificate for {request_number} is ready for collection / download."}
    )
    template_returned, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_RETURNED",
        channel="EMAIL",
        defaults={"template_body": "Your request {request_number} has been returned for corrections."}
    )
    template_rejected, _ = NotificationTemplate.objects.get_or_create(
        event_code="REQ_REJECTED",
        channel="EMAIL",
        defaults={"template_body": "Your request {request_number} could not be processed."}
    )

    requests_config = [
        # 1. UNDER_VERIFICATION
        {
            "request_number": "REQ-2026-0001",
            "student": student_66,
            "service_code": "COE-002",
            "status": "UNDER_VERIFICATION",
            "step_order": 1,
            "submitted_at": create_dt(2026, 8, 28, 10, 15),
            "completed_at": None,
            "field_values": {
                "Purpose of Transcript": "Higher Studies Abroad",
                "Number of Sets / Copies Required": "2",
                "Delivery Mode": "Postal / Courier Delivery",
                "Postal Address with PIN (if courier requested)": "14 Anna Nagar Main Road, Tiruchirappalli - 620020",
                "WES Reference Number (if applicable)": "WES-8923411",
                "Special Instructions / Remarks": "Please seal in official university envelope for WES submission.",
            },
            "documents": [
                ("Copy of Consolidated Mark Statement", "VERIFIED", "documents/2026/08/marksheet_consolidated.pdf"),
                ("Passport Size Photograph", "PENDING", "documents/2026/08/passport_photo.jpg"),
            ],
            "history": [
                ("Draft Saved", "Draft application created by student", create_dt(2026, 8, 28, 9, 30), student_66.user_id, None),
                ("Request Submitted", "Request submitted with online fee payment of Rs. 500", create_dt(2026, 8, 28, 10, 15), student_66.user_id, 1),
                ("Verification Started", "Assigned to COE verification staff for document checks", create_dt(2026, 8, 29, 11, 0), coe_staff or student_66.user_id, 1),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 8, 28, 10, 16)),
                (template_verified, create_dt(2026, 8, 29, 11, 1)),
            ],
        },
        # 2. APPROVED
        {
            "request_number": "REQ-2026-0002",
            "student": student_66,
            "service_code": "COE-004",
            "status": "APPROVED",
            "step_order": 3,
            "submitted_at": create_dt(2026, 8, 20, 14, 20),
            "completed_at": None,
            "field_values": {
                "Month and Year of Passing": "May 2026",
                "Reason for Request": "Higher Studies",
                "No Dues Clearance Declaration": "true",
                "Delivery Mode": "In-Person Collection",
            },
            "documents": [],
            "history": [
                ("Request Submitted", "Pass certificate request submitted", create_dt(2026, 8, 20, 14, 20), student_66.user_id, 1),
                ("Eligibility & Dues Verified", "Verified academic records and no-dues status with department", create_dt(2026, 8, 22, 11, 0), coe_staff or student_66.user_id, 1),
                ("Pass Certificate Prepared", "Pass certificate compiled and verified against master register", create_dt(2026, 8, 22, 16, 30), coe_staff or student_66.user_id, 2),
                ("Approved", "Final approval granted by Controller of Examinations", create_dt(2026, 8, 23, 9, 30), coe_admin or student_66.user_id, 3),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 8, 20, 14, 21)),
                (template_approved, create_dt(2026, 8, 23, 9, 32)),
            ],
        },
        # 3. SUBMITTED
        {
            "request_number": "REQ-2026-0003",
            "student": student_66,
            "service_code": "COE-003",
            "status": "SUBMITTED",
            "step_order": 1,
            "submitted_at": create_dt(2026, 9, 1, 8, 45),
            "completed_at": None,
            "field_values": {
                "Programme Type": "Postgraduate (PG)",
                "Semester Range Required": "All Semesters (Consolidated)",
                "Month and Year of Last Examination": "May 2026",
                "Purpose of Request": "Job / Employment Verification",
                "Delivery Mode": "In-Person Collection",
                "Remarks / Additional Notes": "Needed for campus interview verification.",
            },
            "documents": [],
            "history": [
                ("Request Submitted", "Statement of marks consolidation request submitted", create_dt(2026, 9, 1, 8, 45), student_66.user_id, 1),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 9, 1, 8, 46)),
            ],
        },
        # 4. RETURNED
        {
            "request_number": "REQ-2026-0004",
            "student": student_66,
            "service_code": "COE-005",
            "status": "RETURNED",
            "step_order": 1,
            "submitted_at": create_dt(2026, 8, 25, 16, 10),
            "completed_at": None,
            "field_values": {
                "Correction Type": "Name Correction",
                "Correct Name (as per 10th/12th Certificate)": "Mohamed Jainul Haneef M I",
                "Correct Date of Birth (as per Certificate)": "2000-04-01",
                "Reprint of Mark Statement Required": "Yes",
                "Semester(s) for Reprint": "Semester 1, Semester 2",
                "Remark by the Student": "Initial in marksheet was printed as M instead of M I.",
            },
            "documents": [
                ("Copy of 10th Mark Statement (Proof of Name/DOB)", "REJECTED", "documents/2026/08/10th_marksheet_blur.pdf"),
            ],
            "history": [
                ("Request Submitted", "Submitted application for name correction", create_dt(2026, 8, 25, 16, 10), student_66.user_id, 1),
                ("Returned for Corrections", "Uploaded 10th mark statement is blurry. Please upload high-resolution original scan.", create_dt(2026, 8, 27, 10, 0), coe_staff or student_66.user_id, 1),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 8, 25, 16, 11)),
                (template_returned, create_dt(2026, 8, 27, 10, 1)),
            ],
        },
        # 5. COMPLETED
        {
            "request_number": "REQ-2026-0005",
            "student": student_66,
            "service_code": "COE-002",
            "status": "COMPLETED",
            "step_order": 3,
            "submitted_at": create_dt(2026, 8, 10, 9, 0),
            "completed_at": create_dt(2026, 8, 13, 11, 30),
            "field_values": {
                "Purpose of Transcript": "Job / Employment",
                "Number of Sets / Copies Required": "1",
                "Delivery Mode": "In-Person Collection",
                "Special Instructions / Remarks": "Collected by student directly from COE counter.",
            },
            "documents": [
                ("Copy of Consolidated Mark Statement", "VERIFIED", "documents/2026/08/transcript_final_cms.pdf"),
                ("Passport Size Photograph", "VERIFIED", "documents/2026/08/photo_id.jpg"),
            ],
            "history": [
                ("Request Submitted", "Transcript request submitted", create_dt(2026, 8, 10, 9, 0), student_66.user_id, 1),
                ("Verification Completed", "All transcripts and identity verified", create_dt(2026, 8, 11, 14, 0), coe_staff or student_66.user_id, 1),
                ("Transcript Printed & Sealed", "Transcript certificate set prepared and stamped", create_dt(2026, 8, 12, 16, 30), coe_staff or student_66.user_id, 2),
                ("Approved", "Attested by Controller of Examinations", create_dt(2026, 8, 13, 10, 0), coe_admin or student_66.user_id, 3),
                ("Completed", "Certificate delivered to student at counter. Request closed.", create_dt(2026, 8, 13, 11, 30), coe_admin or student_66.user_id, 3),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 8, 10, 9, 1)),
                (template_approved, create_dt(2026, 8, 13, 10, 1)),
                (template_completed, create_dt(2026, 8, 13, 11, 31)),
            ],
        },
        # 6. DRAFT
        {
            "request_number": "REQ-2026-0006",
            "student": student_66,
            "service_code": "COE-001",
            "status": "DRAFT",
            "step_order": None,
            "submitted_at": None,
            "completed_at": None,
            "field_values": {
                "Semester": "Semester 3",
                "Academic Year / Batch": "2024-2026",
                "Number of Courses for CIA Reappear": "1",
                "Course 1 - Course Code": "MCA302",
                "Course 1 - Course Title": "Distributed Systems",
                "Course 1 - Name of the Course Teacher": "Dr. S. K. Khaja",
                "Reason for CIA Reappear": "Drafting application for reappearance",
            },
            "documents": [],
            "history": [
                ("Draft Created", "Started draft application for CIA Reappear", create_dt(2026, 9, 3, 7, 20), student_66.user_id, None),
            ],
            "notifications": [],
        },
        # 7. REJECTED
        {
            "request_number": "REQ-2026-0007",
            "student": student_66,
            "service_code": "COE-001",
            "status": "REJECTED",
            "step_order": 1,
            "submitted_at": create_dt(2026, 8, 15, 11, 0),
            "completed_at": create_dt(2026, 8, 18, 15, 0),
            "field_values": {
                "Semester": "Semester 2",
                "Academic Year / Batch": "2024-2026",
                "Number of Courses for CIA Reappear": "1",
                "Course 1 - Course Code": "MCA204",
                "Course 1 - Course Title": "Advanced Database Systems",
                "Course 1 - Name of the Course Teacher": "Prof. M. A. Basheer",
                "Reason for CIA Reappear": "Missed assessment due to personal travel",
            },
            "documents": [],
            "history": [
                ("Request Submitted", "Application submitted for CIA reappear exam", create_dt(2026, 8, 15, 11, 0), student_66.user_id, 1),
                ("Rejected", "Attendance criteria not met for CIA reappear eligibility under exam regulations.", create_dt(2026, 8, 18, 15, 0), teacher_user or student_66.user_id, 1),
            ],
            "notifications": [
                (template_submitted, create_dt(2026, 8, 15, 11, 1)),
                (template_rejected, create_dt(2026, 8, 18, 15, 1)),
            ],
        },
    ]

    # Add isolation test request for student_57 if available
    if student_57:
        requests_config.append({
            "request_number": "REQ-2026-0099",
            "student": student_57,
            "service_code": "COE-003",
            "status": "SUBMITTED",
            "step_order": 1,
            "submitted_at": create_dt(2026, 9, 2, 10, 0),
            "completed_at": None,
            "field_values": {
                "Programme Type": "Postgraduate (PG)",
                "Semester Range Required": "Semester 1",
                "Month and Year of Last Examination": "Nov 2025",
                "Purpose of Request": "Higher Studies",
                "Delivery Mode": "In-Person Collection",
            },
            "documents": [],
            "history": [
                ("Request Submitted", "Request submitted by Abdul Rasak", create_dt(2026, 9, 2, 10, 0), student_57.user_id, 1),
            ],
            "notifications": [],
        })

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for item in requests_config:
            service = services[item["service_code"]]
            step = steps_by_service.get(service.code, {}).get(item["step_order"]) if item["step_order"] else None

            req, is_created = Request.objects.update_or_create(
                request_number=item["request_number"],
                defaults={
                    "student_id": item["student"],
                    "service_id": service,
                    "current_status": item["status"],
                    "current_step_id": step,
                    "submitted_at": item["submitted_at"],
                    "completed_at": item["completed_at"],
                },
            )

            if is_created:
                created_count += 1
            else:
                updated_count += 1

            # Populate RequestFieldValue records
            service_fields = {f.field_label: f for f in ServiceField.objects.filter(service_id=service)}
            RequestFieldValue.objects.filter(request_id=req).delete()
            for label, value in item["field_values"].items():
                sf = service_fields.get(label)
                if sf:
                    RequestFieldValue.objects.create(
                        request_id=req,
                        field_id=sf,
                        field_value=value,
                    )

            # Populate Document records
            service_docs = {d.document_name: d for d in ServiceDocument.objects.filter(service_id=service)}
            Document.objects.filter(request_id=req).delete()
            for doc_name, v_status, f_path in item["documents"]:
                sd = service_docs.get(doc_name)
                if sd:
                    Document.objects.create(
                        request_id=req,
                        service_document_id=sd,
                        file_path=f_path,
                        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        verification_status=v_status,
                    )

            # Populate WorkflowHistory records
            WorkflowHistory.objects.filter(request_id=req).delete()
            for action_name, remarks, action_time, action_user, h_step_order in item["history"]:
                h_step = steps_by_service.get(service.code, {}).get(h_step_order) if h_step_order else None
                h_entry = WorkflowHistory.objects.create(
                    request_id=req,
                    step_id=h_step,
                    action_by_user_id=action_user,
                    action=action_name,
                    remarks=remarks,
                )
                # auto_now_add override
                WorkflowHistory.objects.filter(pk=h_entry.pk).update(action_at=action_time)

            # Populate Notification records
            Notification.objects.filter(request_id=req).delete()
            for tmpl, sent_time in item["notifications"]:
                notif = Notification.objects.create(
                    request_id=req,
                    user_id=item["student"].user_id,
                    channel=tmpl.channel,
                    template_id=tmpl,
                    status="SENT",
                    sent_at=sent_time,
                )
                Notification.objects.filter(pk=notif.pk).update(created_at=sent_time)

            print(f"  Processed request {req.request_number} ({req.current_status}) for {item['student'].register_number}")

    print(f"\nRequest seeding completed. Created: {created_count}, Updated: {updated_count}\n")
    return {"created": created_count, "existing": updated_count, "skipped": False}
