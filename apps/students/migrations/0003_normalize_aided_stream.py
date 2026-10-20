from django.db import migrations, models


def normalize_aided_stream(apps, schema_editor):
    student = apps.get_model('students', 'Student')
    student.objects.using(schema_editor.connection.alias).filter(
        stream__iexact='AIDED'
    ).update(stream='Aided')


def restore_aided_stream(apps, schema_editor):
    student = apps.get_model('students', 'Student')
    student.objects.using(schema_editor.connection.alias).filter(
        stream__iexact='Aided'
    ).update(stream='AIDED')


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_alter_student_status'),
    ]

    operations = [
        migrations.RunPython(normalize_aided_stream, restore_aided_stream),
        migrations.AlterField(
            model_name='student',
            name='stream',
            field=models.CharField(
                choices=[
                    ('SFM', 'SFM'),
                    ('SFW', 'SFW'),
                    ('Aided', 'Aided'),
                ],
                default='SFM',
                max_length=10,
            ),
        ),
    ]
