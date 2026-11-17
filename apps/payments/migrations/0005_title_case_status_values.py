from django.db import migrations, models


def title_case_payment_values(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    PaymentVerificationLog = apps.get_model("payments", "PaymentVerificationLog")

    for old_value, new_value in (
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("ISSUE", "Issue"),
    ):
        Payment.objects.filter(payment_status=old_value).update(
            payment_status=new_value
        )

    for old_value, new_value in (("CONFIRM", "Confirm"), ("REJECT", "Reject")):
        PaymentVerificationLog.objects.filter(action=old_value).update(
            action=new_value
        )


def uppercase_payment_values(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    PaymentVerificationLog = apps.get_model("payments", "PaymentVerificationLog")

    for old_value, new_value in (
        ("Pending", "PENDING"),
        ("Success", "SUCCESS"),
        ("Issue", "ISSUE"),
    ):
        Payment.objects.filter(payment_status=old_value).update(
            payment_status=new_value
        )

    for old_value, new_value in (("Confirm", "CONFIRM"), ("Reject", "REJECT")):
        PaymentVerificationLog.objects.filter(action=old_value).update(
            action=new_value
        )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_remove_payment_payment_payment_737330_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(title_case_payment_values, uppercase_payment_values),
        migrations.AlterField(
            model_name="payment",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("Pending", "Pending"),
                    ("Success", "Success"),
                    ("Issue", "Issue"),
                ],
                default="Pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="paymentverificationlog",
            name="action",
            field=models.CharField(
                choices=[("Confirm", "Confirm"), ("Reject", "Reject")],
                max_length=10,
            ),
        ),
    ]
