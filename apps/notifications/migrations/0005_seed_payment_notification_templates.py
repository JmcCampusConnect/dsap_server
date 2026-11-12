from django.db import migrations


TEMPLATES = [
    (
        "PAYMENT_PENDING",
        "Offline payment required for {request_number}",
        "Your application {request_number} was submitted. Collect the physical challan "
        "from {department_name} at {office_address}, pay at the bank, then return the "
        "bank-stamped challan to the department office.",
    ),
    (
        "PAYMENT_REMINDER",
        "Payment reminder for {request_number}",
        "Payment for application {request_number} is pending. Please complete the "
        "physical challan process before the due date and return the stamped challan "
        "to {department_name}.",
    ),
    (
        "PAYMENT_VERIFIED",
        "Payment verified for {request_number}",
        "Payment for application {request_number} has been verified. Your application "
        "has moved to document verification.",
    ),
    (
        "PAYMENT_REJECTED",
        "Payment verification issue for {request_number}",
        "Payment for application {request_number} could not be verified: "
        "{rejection_reason}. Please visit {department_name} at {office_address} "
        "with corrected payment proof.",
    ),
]


def create_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    database = schema_editor.connection.alias
    for event_code, subject, body in TEMPLATES:
        NotificationTemplate.objects.using(database).get_or_create(
            event_code=event_code,
            channel="IN_APP",
            defaults={"subject": subject, "template_body": body},
        )


def remove_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    database = schema_editor.connection.alias
    NotificationTemplate.objects.using(database).filter(
        event_code__in=[item[0] for item in TEMPLATES],
        channel="IN_APP",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0004_notification_message_notification_subject"),
    ]

    operations = [
        migrations.RunPython(create_templates, remove_templates),
    ]
