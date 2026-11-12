from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class PaymentStatuses:
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    ISSUE = "ISSUE"


class Payment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ("CASH", "Cash"),
        ("DD", "Demand draft"),
        ("CHEQUE", "Cheque"),
        ("BANK_COUNTER", "Bank counter"),
    ]

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
        choices=[
            (PaymentStatuses.PENDING, "Pending"),
            (PaymentStatuses.SUCCESS, "Success"),
            (PaymentStatuses.ISSUE, "Issue"),
        ],
        default=PaymentStatuses.PENDING,
    )

    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        null=True,
        blank=True,
    )

    amount_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    payment_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=150, blank=True)
    bank_branch = models.CharField(max_length=150, blank=True)
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    verified_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_payments",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    reminder_count = models.PositiveSmallIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    payment_due_at = models.DateTimeField(null=True, blank=True)

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment'
        indexes = [
            models.Index(fields=["payment_status", "last_reminder_at"]),
        ]

    def __str__(self):
        return f"{self.request_id} - {self.payment_status}"


class PaymentVerificationLog(models.Model):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"

    ACTION_CHOICES = [
        (CONFIRM, "Confirm"),
        (REJECT, "Reject"),
    ]

    id = models.BigAutoField(primary_key=True)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.RESTRICT,
        related_name="verification_history",
    )
    request = models.ForeignKey(
        "requests.Request",
        on_delete=models.RESTRICT,
        related_name="payment_verification_history",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    amount_received = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    payment_date = models.DateField(null=True, blank=True)
    payment_mode = models.CharField(
        max_length=20,
        choices=Payment.PAYMENT_MODE_CHOICES,
        null=True,
        blank=True,
    )
    bank_name = models.CharField(max_length=150, blank=True)
    bank_branch = models.CharField(max_length=150, blank=True)
    receipt_number = models.CharField(max_length=100, null=True, blank=True)
    remarks = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    acted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.RESTRICT,
        related_name="payment_verification_actions",
    )
    acted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payment_verification_log"
        indexes = [
            models.Index(fields=["payment", "acted_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower("receipt_number"),
                condition=Q(receipt_number__isnull=False) & ~Q(receipt_number=""),
                name="unique_payment_verification_receipt",
            ),
        ]

    def __str__(self):
        return f"{self.payment_id} - {self.action}"