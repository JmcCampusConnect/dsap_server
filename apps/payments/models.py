from django.db import models


class Payment(models.Model):
    
    id = models.BigAutoField(primary_key=True)

    request_id = models.OneToOneField(
        'requests.Request',
        on_delete=models.RESTRICT,
        db_column='request_id'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    gateway_txn_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    payment_method = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )

    payment_status = models.CharField(
        max_length=20,
        default='PENDING'
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment'

    def __str__(self):
        return f"{self.request_id} - {self.payment_status}"