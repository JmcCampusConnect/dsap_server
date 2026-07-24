from django.db import models


class Notification(models.Model):

    id = models.BigAutoField(primary_key=True)

    request_id = models.ForeignKey(
        "requests.Request",
        on_delete=models.CASCADE,
        db_column="request_id"
    )

    user_id = models.ForeignKey(
        # "common.User",
        "accounts.User",
        on_delete=models.RESTRICT,
        db_column="user_id"
    )

    channel = models.CharField(max_length=10)

    template_id = models.ForeignKey(
        "NotificationTemplate",
        on_delete=models.RESTRICT,
        db_column="template_id"
    )

    status = models.CharField(
        max_length=20,
        default="QUEUED"
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification"
        indexes = [
            models.Index(fields=["request_id"]),
        ]

    def __str__(self):
        return f"{self.user_id} - {self.status}"


class NotificationTemplate(models.Model):

    id = models.BigAutoField(primary_key=True)
    event_code = models.CharField(max_length=40)
    channel = models.CharField(max_length=10)
    template_body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_template"
        unique_together = (("event_code", "channel"),)

    def __str__(self):
        return f"{self.event_code} ({self.channel})"