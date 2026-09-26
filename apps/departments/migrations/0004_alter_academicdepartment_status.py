from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0003_alter_academicdepartment_category_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE academic_department
                ALTER COLUMN status TYPE varchar(10)
                USING CASE
                    WHEN status = TRUE THEN 'active'
                    WHEN status = FALSE THEN 'inactive'
                    ELSE 'active'
                END;
            """,
            reverse_sql="""
                ALTER TABLE academic_department
                ALTER COLUMN status TYPE boolean
                USING CASE
                    WHEN status = 'active' THEN TRUE
                    WHEN status = 'inactive' THEN FALSE
                    ELSE TRUE
                END;
            """,
        ),
        migrations.AlterField(
            model_name='academicdepartment',
            name='status',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                ],
                default='active',
            ),
        ),
    ]