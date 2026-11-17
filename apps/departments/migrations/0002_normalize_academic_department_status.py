from django.db import migrations


def normalize_academic_department_status(apps, schema_editor):
    AcademicDepartment = apps.get_model("departments", "AcademicDepartment")
    for dept in AcademicDepartment.objects.all():
        raw_status = str(dept.status or "").strip().lower()
        new_status = "active" if raw_status == "active" else "inactive"
        if dept.status != new_status:
            dept.status = new_status
            dept.save(update_fields=["status"])


class Migration(migrations.Migration):

    dependencies = [
        ("departments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            normalize_academic_department_status,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
