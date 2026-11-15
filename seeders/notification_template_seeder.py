import logging
from typing import Any

from apps.notifications.models import NotificationTemplate

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = [
    {
        "event_code": "REQ_SUBMITTED",
        "channel": "EMAIL",
        "name": "Request Submitted",
        "description": "Sent to student when a service request is successfully submitted.",
        "subject": "Application Submitted - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>Your request for <strong>{service_name}</strong> (Request Number: <strong>{request_number}</strong>) "
            "has been successfully submitted on {action_date}.</p>\n"
            "<p>Current Status: <strong>{new_status}</strong></p>\n"
            "<p>You can track the progress of your application on the student portal: "
            "<a href=\"{portal_url}\">{portal_url}</a>.</p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_UNDER_VERIFICATION",
        "channel": "EMAIL",
        "name": "Request Under Verification",
        "description": "Sent to student when a request is forwarded to the next verification step.",
        "subject": "Application Update: Under Verification - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>Your request <strong>{request_number}</strong> for <strong>{service_name}</strong> has been forwarded for verification.</p>\n"
            "<p>Status changed from <em>{previous_status}</em> to <strong>{new_status}</strong> on {action_date}.</p>\n"
            "<p>Remarks: {remarks}</p>\n"
            "<p>Track your request: <a href=\"{portal_url}\">{portal_url}</a></p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_RETURNED",
        "channel": "EMAIL",
        "name": "Request Returned for Correction",
        "description": "Sent to student when a request requires correction or additional documents.",
        "subject": "Action Required: Request Returned - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>Your request <strong>{request_number}</strong> for <strong>{service_name}</strong> has been returned for correction.</p>\n"
            "<p>Status: <strong>{new_status}</strong></p>\n"
            "<p><strong>Remarks / Reason:</strong> {remarks}</p>\n"
            "<p>Please log in to the student portal and update the required details: "
            "<a href=\"{portal_url}\">{portal_url}</a></p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_REJECTED",
        "channel": "EMAIL",
        "name": "Request Rejected",
        "description": "Sent to student when a request is rejected.",
        "subject": "Application Rejected - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>Your request <strong>{request_number}</strong> for <strong>{service_name}</strong> could not be processed and has been rejected.</p>\n"
            "<p>Status: <strong>{new_status}</strong></p>\n"
            "<p><strong>Reason:</strong> {remarks}</p>\n"
            "<p>If you have any queries, please contact the department or check the portal: "
            "<a href=\"{portal_url}\">{portal_url}</a></p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_COMPLETED",
        "channel": "EMAIL",
        "name": "Request Completed",
        "description": "Sent to student when request processing is complete.",
        "subject": "Application Completed - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>We are pleased to inform you that your request <strong>{request_number}</strong> for <strong>{service_name}</strong> has been completed.</p>\n"
            "<p>Status: <strong>{new_status}</strong> on {action_date}.</p>\n"
            "<p>Remarks: {remarks}</p>\n"
            "<p>Your document is ready for collection or digital download on the portal: "
            "<a href=\"{portal_url}\">{portal_url}</a></p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_ISSUED",
        "channel": "EMAIL",
        "name": "Document Issued",
        "description": "Sent to student when the certificate/document is issued.",
        "subject": "Document Issued - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>The document for your request <strong>{request_number}</strong> ({service_name}) has been issued.</p>\n"
            "<p>Status: <strong>{new_status}</strong> on {action_date}.</p>\n"
            "<p>Remarks: {remarks}</p>\n"
            "<p>View application details: <a href=\"{portal_url}\">{portal_url}</a></p>\n"
            "<p>Regards,<br/>Controller of Examinations</p>"
        ),
        "is_active": True,
    },
    {
        "event_code": "REQ_STATUS_UPDATED",
        "channel": "EMAIL",
        "name": "Request Status Updated",
        "description": "Sent when a request status changes outside the standard workflow actions.",
        "subject": "Application Status Update - {request_number}",
        "template_body": (
            "<p>Dear {student_name},</p>\n"
            "<p>The status of your request <strong>{request_number}</strong> for "
            "<strong>{service_name}</strong> changed from <strong>{previous_status}</strong> "
            "to <strong>{new_status}</strong> on {action_date}.</p>\n"
            "<p>Remarks: {remarks}</p>\n"
            "<p>Track your request: <a href=\"{portal_url}\">{portal_url}</a></p>"
        ),
        "is_active": True,
    },
]


def run() -> dict[str, Any]:
    """
    Seed default notification templates safely.
    - Creates missing templates.
    - If a template exists, only fills in missing name/description/subject if blank.
    - Never overwrites custom subjects or customized bodies.
    - Safe to run repeatedly.
    """
    print("\nSeeding default notification templates...\n")
    created = 0
    existing = 0

    for item in DEFAULT_TEMPLATES:
        template, was_created = NotificationTemplate.objects.get_or_create(
            event_code=item["event_code"],
            channel=item["channel"],
            defaults={
                "name": item["name"],
                "description": item["description"],
                "subject": item["subject"],
                "template_body": item["template_body"],
                "is_active": item["is_active"],
            },
        )
        if was_created:
            created += 1
            print(f"  Created template: {template.event_code} ({template.channel})")
        else:
            existing += 1
            updated = False
            # Safely backfill name/description/subject if existing record had empty fields
            if not template.name and item.get("name"):
                template.name = item["name"]
                updated = True
            if not template.description and item.get("description"):
                template.description = item["description"]
                updated = True
            if not template.subject and item.get("subject"):
                template.subject = item["subject"]
                updated = True
            if updated:
                template.save(update_fields=["name", "description", "subject"])
                print(f"  Updated missing metadata for: {template.event_code} ({template.channel})")
            else:
                print(f"  Preserved existing template: {template.event_code} ({template.channel})")

    print(f"\nNotification template seeding completed. Created: {created}, Existing: {existing}")
    return {"created": created, "existing": existing, "skipped": False}
