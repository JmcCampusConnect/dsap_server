from django.db import migrations

ROLES = [
    ("SYSTEM_ADMIN", "Full system access"),
    ("SERVICE_DEPT_ADMIN", "Manage own service department"),
    ("SERVICE_DEPT_STAFF", "Staff of service department"),
    ("STUDENT", "Student self-service"),
    ("SUBJECT_TEACHING_STAFF", "Teaching staff placeholder"),
]

def seed_roles(apps, schema_editor):
    Role = apps.get_model('accounts','Role')
    for name, desc in ROLES:
        Role.objects.get_or_create(name=name, defaults={"description": desc})

def unseed_roles(apps, schema_editor):
    Role = apps.get_model('accounts','Role')
    Role.objects.filter(name__in=[r[0] for r in ROLES]).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_initial'),
    ]
    operations = [
        migrations.RunPython(seed_roles, unseed_roles),
    ]