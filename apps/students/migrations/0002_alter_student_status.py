from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            """
            UPDATE student
            SET status = CASE
                WHEN LOWER(CAST(status AS TEXT)) IN ('active', 'true', '1', 'yes', 'enabled') THEN 1
                ELSE 0
            END
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='student',
            name='status',
            field=models.BooleanField(default=True),
        ),
    ]
