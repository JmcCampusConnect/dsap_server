from django.db import models


class NotificationStatuses(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENDING = "SENDING", "Sending"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"
    UNCERTAIN = "UNCERTAIN", "Outcome uncertain"


class NotificationChannels(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    IN_APP = "IN_APP", "In-App"


class NotificationTemplate(models.Model):

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150, blank=True, default="")
    description = models.TextField(blank=True, default="")
    event_code = models.CharField(max_length=40)
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannels.choices,
        default=NotificationChannels.EMAIL,
    )
    subject = models.CharField(max_length=200, blank=True, default="")
    template_body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_template"
        unique_together = (("event_code", "channel"),)
        ordering = ["event_code", "channel"]

    def __str__(self):
        label = self.name or self.event_code
        return f"{label} ({self.channel})"


class Notification(models.Model):

    id = models.BigAutoField(primary_key=True)

    request_id = models.ForeignKey(
        "requests.Request",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="request_id",
        related_name="notifications",
    )

    user_id = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="user_id",
        related_name="notifications",
    )

    channel = models.CharField(
        max_length=10,
        choices=NotificationChannels.choices,
        default=NotificationChannels.EMAIL,
    )

    template_id = models.ForeignKey(
        "NotificationTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="template_id",
        related_name="notifications",
    )

    recipient_email = models.EmailField(max_length=255, blank=True, default="")
    subject = models.CharField(max_length=200, blank=True, default="")
    message = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=NotificationStatuses.choices,
        default=NotificationStatuses.QUEUED,
    )

    delivery_error = models.TextField(blank=True, default="")
    retry_count = models.PositiveSmallIntegerField(default=0)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")

    event_identifier = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Stable business-event identity for duplicate prevention (e.g. WF_123)",
    )
    event_code = models.CharField(max_length=50, blank=True, default="")
    request_number_snapshot = models.CharField(max_length=50, blank=True, default="")
    is_test = models.BooleanField(default=False)

    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification"
        indexes = [
            models.Index(fields=["request_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["event_code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["event_identifier", "channel"],
                condition=models.Q(is_test=False)
                & ~models.Q(event_identifier__isnull=True)
                & ~models.Q(event_identifier=""),
                name="unique_event_channel_notification",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        target = self.recipient_email or str(self.user_id)
        return f"{self.channel} -> {target} [{self.status}]"
