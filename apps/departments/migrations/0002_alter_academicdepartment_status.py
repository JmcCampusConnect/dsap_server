from django.db import migrations, models


def normalize_status_values(apps, schema_editor):
    department = apps.get_model('departments', 'AcademicDepartment')
    queryset = department.objects.using(schema_editor.connection.alias)
    truthy = {'active', 'true', '1', 't'}

    for primary_key, value in list(queryset.values_list('pk', 'status')):
        normalized = '1' if str(value).strip().lower() in truthy else '0'
        queryset.filter(pk=primary_key).update(status=normalized)


def restore_status_values(apps, schema_editor):
    department = apps.get_model('departments', 'AcademicDepartment')
    queryset = department.objects.using(schema_editor.connection.alias)

    for primary_key, value in list(queryset.values_list('pk', 'status')):
        normalized = 'ACTIVE' if str(value).strip().lower() in {'1', 'true', 't'} else 'INACTIVE'
        queryset.filter(pk=primary_key).update(status=normalized)


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_status_values, restore_status_values),
        migrations.AlterField(
            model_name='academicdepartment',
            name='status',
            field=models.BooleanField(default=True),
        ),
    ]
