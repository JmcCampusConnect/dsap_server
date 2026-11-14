from django.db import migrations


PLACEHOLDER_REPLACEMENTS = (
    ("Office hours: {office_hours}", ""),
    ("Hours: {office_hours}", ""),
    ("Phone: {contact_phone}", ""),
    (" at {office_address}", ""),
    ("{office_address}", ""),
    ("{office_hours}", ""),
    ("{contact_phone}", ""),
)


def remove_department_office_placeholders(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    templates = NotificationTemplate.objects.using(schema_editor.connection.alias)
    for template in list(templates.all()):
        subject = template.subject
        body = template.template_body
        for old_text, new_text in PLACEHOLDER_REPLACEMENTS:
            subject = subject.replace(old_text, new_text)
            body = body.replace(old_text, new_text)
        if subject != template.subject or body != template.template_body:
            templates.filter(pk=template.pk).update(
                subject=subject,
                template_body=body,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_seed_payment_notification_templates"),
    ]

    operations = [
        migrations.RunPython(
            remove_department_office_placeholders,
            migrations.RunPython.noop,
        ),
    ]
