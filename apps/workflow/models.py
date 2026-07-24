from django.db import models


class WorkflowStep(models.Model):

    id = models.BigAutoField(primary_key=True)

    service_id = models.ForeignKey(
        'services.Service',
        on_delete=models.CASCADE,
        db_column='service_id'
    )

    step_order = models.SmallIntegerField()
    step_name = models.CharField(max_length=150)

    responsible_role_id = models.ForeignKey(

        # 'common.Role',
        'accounts.Role',

        on_delete=models.RESTRICT,
        db_column='responsible_role_id'
    )

    action_type = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_step'
        unique_together = (('service_id', 'step_order'),)

    def __str__(self):
        return f"{self.service_id} - Step {self.step_order}"


class WorkflowHistory(models.Model):

    id = models.BigAutoField(primary_key=True)

    request_id = models.ForeignKey(
        'requests.Request',
        on_delete=models.CASCADE,
        db_column='request_id'
    )

    step_id = models.ForeignKey(
        'workflow.WorkflowStep',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_column='step_id'
    )

    action_by_user_id = models.ForeignKey(
        # 'common.User',
        'accounts.User',
        on_delete=models.RESTRICT,
        db_column='action_by_user_id'
    )

    action = models.CharField(max_length=30)

    remarks = models.TextField(
        null=True,
        blank=True
    )

    action_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workflow_history'
        indexes = [
            models.Index(fields=['request_id', 'action_at']),
        ]

    def __str__(self):
        return f"{self.request_id} - {self.action}"