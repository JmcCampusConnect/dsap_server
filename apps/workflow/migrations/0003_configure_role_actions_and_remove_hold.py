from django.db import migrations


ROLE_REQUIRED_ACTIONS = {
    "SERVICE_DEPT_STAFF": "FORWARD",
    "SERVICE_DEPT_ADMIN": "APPROVE",
}
ROLE_DISALLOWED_ACTIONS = {
    "SERVICE_DEPT_STAFF": {"APPROVE"},
    "SERVICE_DEPT_ADMIN": {"FORWARD"},
}
VALID_ACTIONS = {"APPROVE", "REJECT", "RETURN", "FORWARD", "COMPLETE"}


def configure_existing_workflow_actions(apps, schema_editor):
    WorkflowStep = apps.get_model("workflow", "WorkflowStep")

    for step in WorkflowStep.objects.select_related("responsible_role_id").iterator():
        existing_actions = step.allowed_actions if isinstance(step.allowed_actions, list) else []
        actions = []
        role_name = step.responsible_role_id.name
        disallowed_actions = ROLE_DISALLOWED_ACTIONS.get(role_name, set())
        for action in existing_actions:
            normalized = action.strip().upper() if isinstance(action, str) else ""
            if (
                normalized in VALID_ACTIONS
                and normalized not in disallowed_actions
                and normalized not in actions
            ):
                actions.append(normalized)

        required_action = ROLE_REQUIRED_ACTIONS.get(role_name)
        if required_action and required_action not in actions:
            actions.append(required_action)

        if actions != existing_actions:
            step.allowed_actions = actions
            step.save(update_fields=["allowed_actions"])


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0002_alter_workflowstep_options_and_more"),
    ]

    operations = [
        migrations.RunPython(configure_existing_workflow_actions, migrations.RunPython.noop),
    ]
