from rest_framework import serializers
from django.db import models, transaction
from apps.services.models import Service, ServiceField, ServiceDocument
from apps.departments.models import ServiceDepartment
from apps.workflow.models import WorkflowStep
from apps.workflow.serializers import WorkflowStepSerializer
from apps.accounts.models import Role
from apps.workflow.constants import ActionTypes, AllowedActions
from apps.audit.models import AuditLog


class ServiceDepartmentRefSerializer(serializers.ModelSerializer):
    """Minimal nested representation of the department inside Service responses."""

    class Meta:
        model = ServiceDepartment
        fields = ["id", "code", "name"]


class ServiceFieldSerializer(serializers.ModelSerializer):
    """Serializer for configuring dynamic service fields."""

    class Meta:
        model = ServiceField
        fields = [
            "id",
            "service_id",
            "field_label",
            "field_type",
            "is_required",
            "display_order",
            "options_json",
            "conditional_logic",
        ]
        read_only_fields = ["id", "service_id"]

    def validate(self, data):
        field_type = data.get("field_type")
        options_json = data.get("options_json")
        
        if not field_type:
            raise serializers.ValidationError({"field_type": "field_type is required"})
        
        if field_type in ["DROPDOWN", "RADIO", "CHECKBOX", "SELECT"]:
            if not options_json or not isinstance(options_json, list) or len(options_json) == 0:
                raise serializers.ValidationError({
                    "options_json": f"options_json must be a non-empty list for {field_type} fields."
                })
        else:
            # Remove options_json for non-select field types
            if options_json:
                data.pop("options_json", None)
        
        return data


class ServiceSerializer(serializers.ModelSerializer):
    """
    Full serializer for Service CRUD.

    Read  → returns nested `service_department` object {id, code, name}, `custom_fields`, and `workflow_steps`
    Write → accepts `service_department_id` as an integer FK, plus optional `custom_fields` and `workflow_steps`
    """

    service_department = ServiceDepartmentRefSerializer(
        source="service_department_id", 
        read_only=True,
    )
    custom_fields = serializers.SerializerMethodField(read_only=True)
    workflow_steps = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Service
        fields = [
            "id",
            "code",
            "name",
            "service_department",
            "service_department_id",
            "base_fee",
            "sla_days",
            "status",
            "created_at",
            "updated_at",
            "custom_fields",
            "workflow_steps",
        ]
        read_only_fields = ["id", "code", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "service_department_id": {"write_only": True},
        }

    def get_custom_fields(self, obj):
        fields = ServiceField.objects.filter(service_id=obj).order_by("display_order", "id")
        return ServiceFieldSerializer(fields, many=True).data

    def get_workflow_steps(self, obj):
        steps = WorkflowStep.objects.filter(service_id=obj).select_related("responsible_role_id").order_by("step_order", "id")
        return WorkflowStepSerializer(steps, many=True).data

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        custom_fields_data = self.initial_data.get("custom_fields")
        if custom_fields_data is not None and isinstance(custom_fields_data, list):
            self._save_custom_fields(instance, custom_fields_data)

        workflow_steps_data = self.initial_data.get("workflow_steps")
        if workflow_steps_data is not None and isinstance(workflow_steps_data, list):
            self._save_workflow_steps(instance, workflow_steps_data)

        return instance

    def create(self, validated_data):
        instance = super().create(validated_data)

        custom_fields_data = self.initial_data.get("custom_fields")
        if custom_fields_data is not None and isinstance(custom_fields_data, list):
            self._save_custom_fields(instance, custom_fields_data)

        workflow_steps_data = self.initial_data.get("workflow_steps")
        if workflow_steps_data is not None and isinstance(workflow_steps_data, list):
            self._save_workflow_steps(instance, workflow_steps_data)

        return instance

    def _save_custom_fields(self, service, custom_fields_data):
        existing_fields = {f.id: f for f in ServiceField.objects.filter(service_id=service)}
        kept_ids = set()
        id_map = {}

        created_or_updated = []
        for index, item in enumerate(custom_fields_data):
            field_id_raw = item.get("id")
            label = item.get("field_label") or item.get("label") or ""
            ftype = (item.get("field_type") or item.get("type") or "TEXT").upper()
            is_req = item.get("is_required", item.get("required", False))
            display_order = item.get("display_order", item.get("order", index + 1))
            options_json = item.get("options_json", item.get("options", None))

            existing_obj = None
            if field_id_raw is not None:
                try:
                    int_id = int(field_id_raw)
                    existing_obj = existing_fields.get(int_id)
                except (ValueError, TypeError):
                    existing_obj = None

            if existing_obj:
                existing_obj.field_label = label
                existing_obj.field_type = ftype
                existing_obj.is_required = is_req
                existing_obj.display_order = display_order
                existing_obj.options_json = options_json
                existing_obj.save()
                field_obj = existing_obj
            else:
                field_obj = ServiceField.objects.create(
                    service_id=service,
                    field_label=label,
                    field_type=ftype,
                    is_required=is_req,
                    display_order=display_order,
                    options_json=options_json,
                )

            kept_ids.add(field_obj.id)
            if field_id_raw is not None:
                id_map[str(field_id_raw)] = field_obj.id
            created_or_updated.append((field_obj, item.get("conditional_logic")))

        for field_obj, logic in created_or_updated:
            if logic:
                if isinstance(logic, dict):
                    logic_copy = dict(logic)
                    dep_id = str(logic_copy.get("depends_on_field_id", ""))
                    if dep_id in id_map:
                        logic_copy["depends_on_field_id"] = id_map[dep_id]
                    field_obj.conditional_logic = logic_copy
                elif isinstance(logic, list):
                    updated_list = []
                    for rule in logic:
                        if isinstance(rule, dict):
                            r_copy = dict(rule)
                            dep_id = str(r_copy.get("depends_on_field_id", ""))
                            if dep_id in id_map:
                                r_copy["depends_on_field_id"] = id_map[dep_id]
                            updated_list.append(r_copy)
                        else:
                            updated_list.append(rule)
                    field_obj.conditional_logic = updated_list
            else:
                field_obj.conditional_logic = None

            field_obj.save()

        ServiceField.objects.filter(service_id=service).exclude(id__in=kept_ids).delete()

    @transaction.atomic
    def _save_workflow_steps(self, service, workflow_steps_data):
        request = self.context.get("request")
        existing_steps = {s.id: s for s in WorkflowStep.objects.filter(service_id=service)}
        kept_ids = set()

        # Temporary step_order offset to avoid unique constraint collision during reordering
        WorkflowStep.objects.filter(service_id=service).update(step_order=models.F('step_order') + 1000)

        for index, item in enumerate(workflow_steps_data):
            step_id_raw = item.get("id")
            step_name = (item.get("step_name") or item.get("name") or "").strip()
            if not step_name:
                continue

            role_id_val = item.get("responsible_role_id")
            role_obj = None
            if role_id_val is not None:
                try:
                    if isinstance(role_id_val, int) or (isinstance(role_id_val, str) and role_id_val.isdigit()):
                        role_obj = Role.objects.get(id=int(role_id_val))
                    else:
                        role_obj = Role.objects.filter(name=str(role_id_val)).first()
                except Role.DoesNotExist:
                    role_obj = None

            if not role_obj:
                role_obj = Role.objects.exclude(name="STUDENT").first() or Role.objects.first()

            action_type = (item.get("action_type") or "APPROVAL").strip().upper()
            if action_type not in ActionTypes.all():
                action_type = ActionTypes.APPROVAL

            raw_actions = item.get("allowed_actions")
            if raw_actions is None or not isinstance(raw_actions, list):
                allowed_actions = [AllowedActions.APPROVE, AllowedActions.REJECT]
            else:
                allowed_actions = [
                    a.strip().upper() for a in raw_actions
                    if isinstance(a, str) and a.strip().upper() in AllowedActions.all()
                ]
                if not allowed_actions:
                    allowed_actions = [AllowedActions.APPROVE, AllowedActions.REJECT]

            step_order = index + 1

            existing_obj = None
            if step_id_raw is not None:
                try:
                    int_id = int(step_id_raw)
                    existing_obj = existing_steps.get(int_id)
                except (ValueError, TypeError):
                    existing_obj = None

            if existing_obj:
                old_data = WorkflowStepSerializer(existing_obj).data
                existing_obj.step_name = step_name
                existing_obj.responsible_role_id = role_obj
                existing_obj.action_type = action_type
                existing_obj.allowed_actions = allowed_actions
                existing_obj.step_order = step_order
                existing_obj.save()
                step_obj = existing_obj

                new_data = WorkflowStepSerializer(step_obj).data
                changes = {}
                for k, new_val in new_data.items():
                    old_val = old_data.get(k)
                    if old_val != new_val:
                        changes[k] = {"old": old_val, "new": new_val}
                if changes:
                    AuditLog.log(
                        request=request,
                        action="UPDATE",
                        obj=step_obj,
                        object_id=str(step_obj.id),
                        object_repr=str(step_obj),
                        changes=changes,
                    )
            else:
                step_obj = WorkflowStep.objects.create(
                    service_id=service,
                    step_name=step_name,
                    responsible_role_id=role_obj,
                    action_type=action_type,
                    allowed_actions=allowed_actions,
                    step_order=step_order,
                )
                AuditLog.log(
                    request=request,
                    action="CREATE",
                    obj=step_obj,
                    object_id=str(step_obj.id),
                    object_repr=str(step_obj),
                    changes=WorkflowStepSerializer(step_obj).data,
                )

            kept_ids.add(step_obj.id)

        deleted_steps = WorkflowStep.objects.filter(service_id=service).exclude(id__in=kept_ids)
        for del_step in deleted_steps:
            del_id = str(del_step.id)
            del_repr = str(del_step)
            snapshot = WorkflowStepSerializer(del_step).data
            del_step.delete()
            AuditLog.log(
                request=request,
                action="DELETE",
                app_label="workflow",
                model_name="WorkflowStep",
                object_id=del_id,
                object_repr=del_repr,
                changes=snapshot,
            )


class ServiceDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDocument
        fields = [
            "id",
            "service_id",
            "document_name",
            "is_mandatory",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "service_id", "created_at", "updated_at"]  
    
    def validate_document_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Document name cannot be empty")
        return value.strip()

class WorkflowStepSerializer(serializers.ModelSerializer):
    """Serializer for workflow steps associated with a service."""
    class Meta:
        model = WorkflowStep
        fields = [
            "id",
            "step_order",
            "step_name",
            "action_type",
            "responsible_role_id",
        ]

class ServiceDirectoryDepartmentSerializer(serializers.ModelSerializer):
    """Department with a list of enabled services."""
    services = serializers.SerializerMethodField()

    class Meta:
        model = ServiceDepartment
        fields = ['id', 'code', 'name', 'services']

    def get_services(self, obj):
        enabled_services = obj.service_set.filter(status='ENABLED').order_by('name')
        return ServiceSerializer(enabled_services, many=True).data


class ServiceDetailSerializer(ServiceSerializer):
    """Full service detail including fields and documents, and workflow steps."""
    documents = serializers.SerializerMethodField()
    workflow_steps = serializers.SerializerMethodField()

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ['documents', 'description', 'workflow_steps']

    def get_documents(self, obj):
        docs = ServiceDocument.objects.filter(service_id=obj).order_by('document_name')
        return ServiceDocumentSerializer(docs, many=True).data
    
    def get_workflow_steps(self, obj):
        steps = WorkflowStep.objects.filter(service_id=obj).order_by('step_order')
        return WorkflowStepSerializer(steps, many=True).data


class ServiceDepartmentWithCountSerializer(serializers.ModelSerializer):
    service_count = serializers.IntegerField()

    class Meta:
        model = ServiceDepartment
        fields = ['id', 'code', 'name', 'service_count']