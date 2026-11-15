from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="payment",
            name="gateway_txn_id",
        ),
        migrations.RemoveField(
            model_name="payment",
            name="payment_method",
        ),
        migrations.RemoveField(
            model_name="payment",
            name="payment_mode",
        ),
        migrations.RemoveField(
            model_name="payment",
            name="bank_name",
        ),
        migrations.RemoveField(
            model_name="payment",
            name="bank_branch",
        ),
        migrations.RemoveField(
            model_name="paymentverificationlog",
            name="payment_mode",
        ),
        migrations.RemoveField(
            model_name="paymentverificationlog",
            name="bank_name",
        ),
        migrations.RemoveField(
            model_name="paymentverificationlog",
            name="bank_branch",
        ),
    ]
