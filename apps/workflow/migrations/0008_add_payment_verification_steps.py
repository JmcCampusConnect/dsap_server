from django.db import migrations


PAYMENT_STEP_NAME = "Payment Verification"
TEMPORARY_ORDER_OFFSET = 10000


def add_payment_steps(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    Role = apps.get_model("accounts", "Role")
    WorkflowStep = apps.get_model("workflow", "WorkflowStep")

    fee_services = list(Service.objects.filter(base_fee__gt=0))
    if not fee_services:
        return
    staff_role, _ = Role.objects.get_or_create(
        name="SERVICE_DEPT_STAFF",
        defaults={"description": "Service department staff"},
    )

    for service in fee_services:
        if WorkflowStep.objects.filter(
            service_id=service.pk,
            step_kind="PAYMENT_VERIFY",
        ).exists():
            continue

        steps = WorkflowStep.objects.filter(service_id=service.pk)
        steps.update(step_order=models_f("step_order") + TEMPORARY_ORDER_OFFSET)
        steps.update(
            step_order=models_f("step_order") - TEMPORARY_ORDER_OFFSET + 1
        )
        WorkflowStep.objects.create(
            service_id=service,
            step_order=1,
            step_name=PAYMENT_STEP_NAME,
            step_kind="PAYMENT_VERIFY",
            responsible_role_id=staff_role,
            allowed_actions=["CONFIRM_PAYMENT", "REJECT_PAYMENT"],
        )


def remove_payment_steps(apps, schema_editor):
    Request = apps.get_model("requests", "Request")
    WorkflowHistory = apps.get_model("workflow", "WorkflowHistory")
    WorkflowStep = apps.get_model("workflow", "WorkflowStep")

    for payment_step in WorkflowStep.objects.filter(step_kind="PAYMENT_VERIFY"):
        verification_step = (
            WorkflowStep.objects.filter(
                service_id=payment_step.service_id,
                step_kind="VERIFICATION",
            )
            .order_by("step_order", "pk")
            .first()
        )
        if verification_step:
            Request.objects.filter(current_step_id=payment_step.pk).update(
                current_step_id=verification_step.pk
            )
            WorkflowHistory.objects.filter(step_id=payment_step.pk).update(
                step_id=verification_step.pk
            )

        payment_step.delete()

    services = (
        WorkflowStep.objects.values_list("service_id", flat=True).distinct()
    )
    for service_id in services:
        steps = WorkflowStep.objects.filter(service_id=service_id)
        steps.update(step_order=models_f("step_order") + TEMPORARY_ORDER_OFFSET)
        steps.update(
            step_order=models_f("step_order") - TEMPORARY_ORDER_OFFSET - 1
        )


def models_f(field_name):
    from django.db.models import F

    return F(field_name)


class Migration(migrations.Migration):
    dependencies = [
        ("workflow", "0007_alter_workflowstep_step_kind"),
        ("services", "0002_alter_service_status"),
    ]

    operations = [
        migrations.RunPython(add_payment_steps, remove_payment_steps),
    ]
