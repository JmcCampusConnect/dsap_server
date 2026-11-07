from django.db import migrations, models


VALID_ACTIONS = {"FORWARD", "RETURN", "REJECT", "COMPLETE", "ISSUE"}


def migrate_workflow_actions_and_statuses(apps, schema_editor):
    WorkflowStep = apps.get_model("workflow", "WorkflowStep")
    Request = apps.get_model("requests", "Request")

    for step in WorkflowStep.objects.all().iterator():
        existing_actions = step.allowed_actions if isinstance(step.allowed_actions, list) else []
        actions = []
        for action in existing_actions:
            normalized = action.strip().upper() if isinstance(action, str) else ""
            if normalized in VALID_ACTIONS and normalized not in actions:
                actions.append(normalized)

        if step.step_order == 3 and "COMPLETE" not in actions:
            actions.append("COMPLETE")
        if step.step_order == 4:
            actions = ["ISSUE"]

        updates = {}
        if actions != existing_actions:
            updates["allowed_actions"] = actions
        if step.action_type == "APPROVAL":
            updates["action_type"] = "REVIEW"
        if updates:
            WorkflowStep.objects.filter(pk=step.pk).update(**updates)

    Request.objects.filter(current_status__in=["APPROVED", "COMPLETED"]).update(
        current_status="ISSUED",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0003_configure_role_actions_and_remove_hold"),
        ("requests", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_workflow_actions_and_statuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="workflowstep",
            name="allowed_actions",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of allowed action codes for this step, e.g. ['FORWARD', 'RETURN', 'COMPLETE', 'ISSUE']",
            ),
        ),
    ]
