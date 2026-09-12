from django.db import models, transaction
from django.utils import timezone


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
    
    @classmethod
    def generate_request_number(cls, dept_code: str) -> str:
        """
        Produce a request number in the format {DEPT_CODE}{YYYY}{seq:05d}, e.g. COE202600145.
        The sequence is scoped per department per year. A row lock on the latest
        matching request is used to prevent duplicates under concurrent creation.
        """
        year = timezone.now().year
        prefix = f"{(dept_code or 'REQ').upper()}{year}"

        with transaction.atomic():
            latest = (
                cls.objects
                .select_for_update()
                .filter(request_number__startswith=prefix)
                .order_by('-request_number')
                .first()
            )

            next_seq = 1
            if latest:
                try:
                    next_seq = int(latest.request_number[len(prefix):]) + 1
                except (ValueError, TypeError):
                    next_seq = 1

        return f"{prefix}{next_seq:05d}"

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