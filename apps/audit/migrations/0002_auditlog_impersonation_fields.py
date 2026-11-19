from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        # Add impersonator tracking fields
        migrations.AddField(
            model_name='auditlog',
            name='impersonator_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='impersonator_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[('CREATE', 'Create'), ('UPDATE', 'Update'), ('ACTIVATE', 'Activate'), ('DEACTIVATE', 'Deactivate'), ('DELETE', 'Delete'), ('VIEW', 'View'), ('LOGIN', 'Login'), ('LOGOUT', 'Logout'), ('UPLOAD', 'Upload'), ('EXPORT', 'Export'), ('IMPORT', 'Import'), ('IMPERSONATE_START', 'Impersonate Start'), ('IMPERSONATE_END', 'Impersonate End'), ('IMPERSONATED_REQUEST', 'Impersonated Request')], max_length=50),
        ),
    ]
