from django.db import migrations


def replace_under_verification(apps, schema_editor):
    Request = apps.get_model("requests", "Request")
    Document = apps.get_model("documents", "Document")
    ServiceDocument = apps.get_model("services", "ServiceDocument")

    database = schema_editor.connection.alias
    requests = (
        Request.objects.using(database)
        .filter(current_status="UNDER_VERIFICATION")
        .select_related("current_step_id", "service_id")
    )

    for request in requests.iterator():
        step_kind = request.current_step_id.step_kind if request.current_step_id else ""
        if step_kind in {"PROCESSING", "COMPLETION", "CUSTOM"}:
            new_status = "PROCESSING"
        elif step_kind == "ISSUANCE":
            new_status = "COMPLETED"
        else:
            mandatory_ids = set(
                ServiceDocument.objects.using(database)
                .filter(service_id=request.service_id_id, is_mandatory=True)
                .values_list("id", flat=True)
            )
            documents = list(
                Document.objects.using(database)
                .filter(request_id=request.pk)
                .values("service_document_id_id", "verification_status")
            )
            uploaded_ids = {
                document["service_document_id_id"]
                for document in documents
            }
            all_verified = (
                mandatory_ids.issubset(uploaded_ids)
                and all(
                    document["verification_status"] == "VERIFIED"
                    for document in documents
                )
            )
            new_status = "VERIFIED" if all_verified else "SUBMITTED"

        Request.objects.using(database).filter(pk=request.pk).update(
            current_status=new_status
        )


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0003_add_rejection_remarks_to_document"),
        ("requests", "0002_initial"),
        ("services", "0002_alter_service_status"),
        ("workflow", "0006_remove_workflowstep_action_type"),
    ]

    operations = [
        migrations.RunPython(replace_under_verification, migrations.RunPython.noop),
    ]
