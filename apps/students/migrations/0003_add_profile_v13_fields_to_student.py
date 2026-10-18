import apps.students.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0002_alter_student_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="religion",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="aadhaar_number",
            field=apps.students.fields.EncryptedTextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="parent_name",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="student",
            name="parent_mobile",
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
    ]