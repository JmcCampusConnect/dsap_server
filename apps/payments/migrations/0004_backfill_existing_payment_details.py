from django.db import migrations


def backfill_existing_payment_details(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    database = schema_editor.connection.alias

    for payment in Payment.objects.using(database).filter(payment_status="SUCCESS"):
        payment.amount_received = payment.amount
        payment.payment_date = payment.paid_at.date() if payment.paid_at else None
        payment.payment_mode = (
            payment.payment_method
            if payment.payment_method
            in {"CASH", "DD", "CHEQUE", "BANK_COUNTER"}
            else None
        )
        payment.save(
            using=database,
            update_fields=["amount_received", "payment_date", "payment_mode"],
        )


def clear_backfilled_payment_details(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    database = schema_editor.connection.alias

    for payment in Payment.objects.using(database).filter(payment_status="SUCCESS"):
        if payment.amount_received != payment.amount:
            continue
        if payment.payment_date != (payment.paid_at.date() if payment.paid_at else None):
            continue
        payment.amount_received = None
        payment.payment_date = None
        payment.payment_mode = None
        payment.save(
            using=database,
            update_fields=["amount_received", "payment_date", "payment_mode"],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0003_paymentverificationlog_payment_amount_received_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_existing_payment_details,
            clear_backfilled_payment_details,
        ),
    ]
