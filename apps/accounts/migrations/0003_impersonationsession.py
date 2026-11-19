import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImpersonationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField()),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                (
                    'admin_user',
                    models.ForeignKey(
                        db_column='admin_user_id',
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name='impersonation_sessions_started',
                        to='accounts.user',
                    ),
                ),
                (
                    'target_user',
                    models.ForeignKey(
                        db_column='target_user_id',
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name='impersonation_sessions_received',
                        to='accounts.user',
                    ),
                ),
            ],
            options={
                'db_table': 'impersonation_session',
            },
        ),
        migrations.AddIndex(
            model_name='impersonationsession',
            index=models.Index(fields=['admin_user', 'is_active'], name='impersonati_admin_u_45c0da_idx'),
        ),
        migrations.AddIndex(
            model_name='impersonationsession',
            index=models.Index(fields=['target_user', 'is_active'], name='impersonati_target__c78698_idx'),
        ),
    ]
