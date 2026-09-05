# Generated manually for safe PostgreSQL type conversion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='academicdepartment',
                    name='status',
                    field=models.BooleanField(default=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE academic_department ALTER COLUMN status DROP DEFAULT; "
                        "ALTER TABLE academic_department ALTER COLUMN status TYPE boolean "
                        "USING (CASE WHEN UPPER(status::text) IN ('ACTIVE', 'TRUE', '1', 'T') THEN TRUE ELSE FALSE END); "
                        "ALTER TABLE academic_department ALTER COLUMN status SET DEFAULT TRUE;"
                    ),
                    reverse_sql=(
                        "ALTER TABLE academic_department ALTER COLUMN status DROP DEFAULT; "
                        "ALTER TABLE academic_department ALTER COLUMN status TYPE varchar(10) "
                        "USING (CASE WHEN status IS TRUE THEN 'ACTIVE' ELSE 'INACTIVE' END); "
                        "ALTER TABLE academic_department ALTER COLUMN status SET DEFAULT 'ACTIVE';"
                    ),
                ),
            ],
        ),
    ]
