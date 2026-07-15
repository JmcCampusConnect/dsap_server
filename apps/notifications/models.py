from django.db import models

class Notification(models.Model):
    request_id = models.ForeignKey('requests.Request', on_delete=models.CASCADE, db_column='request_id')
    user_id = models.ForeignKey('common.User', on_delete=models.RESTRICT, db_column='user_id')
    channel = models.CharField(max_length=10)
    template_id = models.ForeignKey('common.NotificationTemplate', on_delete=models.RESTRICT, db_column='template_id')
    status = models.CharField(max_length=20, default='QUEUED')
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notification'
        indexes = [
            models.Index(fields=['request_id']),
        ]
