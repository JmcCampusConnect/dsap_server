from django.db import models


class Request(models.Model):

    id = models.BigAutoField(primary_key=True)

    request_number = models.CharField(
        max_length=30,
        unique=True
    )

    student_id = models.ForeignKey(
        'students.Student',
        on_delete=models.RESTRICT,
        db_column='student_id'
    )

    service_id = models.ForeignKey(
        'services.Service',
        on_delete=models.RESTRICT,
        db_column='service_id'
    )

    current_status = models.CharField(
        max_length=30,
        default='DRAFT'
    )

    current_step_id = models.ForeignKey(
        'workflow.WorkflowStep',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='current_step_id'
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'request'
        indexes = [
            models.Index(fields=['student_id', 'current_status']),
            models.Index(fields=['service_id', 'current_status']),
        ]

    def __str__(self):
        return self.request_number


from django.db import models


class RequestFieldValue(models.Model):

    id = models.BigAutoField(primary_key=True)

    request_id = models.ForeignKey(
        'requests.Request',
        on_delete=models.CASCADE,
        db_column='request_id'
    )

    field_id = models.ForeignKey(
        'services.ServiceField',
        on_delete=models.RESTRICT,
        db_column='field_id'
    )

    field_value = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'request_field_value'

    def __str__(self):
        return f"{self.request_id} - {self.field_id}"