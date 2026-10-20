from django.db import migrations, models


def convert_status_to_strings(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            """
            ALTER TABLE academic_department
            ALTER COLUMN status TYPE varchar(10)
            USING CASE
                WHEN status IS TRUE THEN 'active'
                WHEN status IS FALSE THEN 'inactive'
                ELSE 'active'
            END;
            """
        )
    elif vendor == 'sqlite':
        schema_editor.execute(
            """
            UPDATE academic_department
            SET status = CASE WHEN status THEN 'active' ELSE 'inactive' END;
            """
        )
    else:
        raise NotImplementedError(
            f"Academic department status conversion is not supported for {vendor}."
        )


def convert_status_to_boolean_values(apps, schema_editor):
    schema_editor.execute(
        """
        UPDATE academic_department
        SET status = CASE
            WHEN LOWER(CAST(status AS TEXT)) IN ('active', 'true', '1', 't') THEN '1'
            ELSE '0'
        END;
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ('departments', '0003_alter_academicdepartment_category_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_status_to_strings, migrations.RunPython.noop),
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
        migrations.RunPython(
            migrations.RunPython.noop,
            convert_status_to_boolean_values,
        ),
    ]
