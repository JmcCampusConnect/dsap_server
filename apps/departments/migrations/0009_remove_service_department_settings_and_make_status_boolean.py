from django.db import migrations, models


def convert_status_to_boolean(apps, schema_editor):
    ServiceDepartment = apps.get_model("departments", "ServiceDepartment")
    database = schema_editor.connection.alias
    departments = ServiceDepartment.objects.using(database)

    for pk, status in list(departments.values_list("pk", "status")):
        is_active = str(status).strip().lower() in {"active", "true", "1", "yes"}
        departments.filter(pk=pk).update(status="1" if is_active else "0")


def convert_status_to_text(apps, schema_editor):
    ServiceDepartment = apps.get_model("departments", "ServiceDepartment")
    database = schema_editor.connection.alias
    departments = ServiceDepartment.objects.using(database)

    for pk, status in list(departments.values_list("pk", "status")):
        is_active = str(status).strip().lower() in {"active", "true", "1", "yes"}
        departments.filter(pk=pk).update(status="active" if is_active else "inactive")


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0008_servicedepartment_payment_max_reminders"),
    ]

    operations = [
        migrations.RunPython(convert_status_to_boolean, convert_status_to_text),
        migrations.AlterField(
            model_name="servicedepartment",
            name="status",
            field=models.BooleanField(default=True),
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="office_address",
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="office_hours",
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="contact_phone",
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="payment_due_days",
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="payment_reminder_days",
        ),
        migrations.RemoveField(
            model_name="servicedepartment",
            name="payment_max_reminders",
        ),
    ]
