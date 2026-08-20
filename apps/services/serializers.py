from rest_framework import serializers
from apps.services.models import Service, ServiceField, ServiceDocument
from apps.departments.models import ServiceDepartment
from apps.workflow.models import WorkflowStep


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

    Read  → returns nested `service_department` object {id, code, name} and `custom_fields`
    Write → accepts `service_department_id` as an integer FK, plus optional `custom_fields`
    """

    service_department = ServiceDepartmentRefSerializer(
        source="service_department_id", 
        read_only=True,
    )
    custom_fields = serializers.SerializerMethodField(read_only=True)

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
        ]
        read_only_fields = ["id", "code", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "service_department_id": {"write_only": True},
        }

    def get_custom_fields(self, obj):
        fields = ServiceField.objects.filter(service_id=obj).order_by("display_order", "id")
        return ServiceFieldSerializer(fields, many=True).data

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        custom_fields_data = self.initial_data.get("custom_fields")
        if custom_fields_data is not None and isinstance(custom_fields_data, list):
            self._save_custom_fields(instance, custom_fields_data)

        return instance

    def create(self, validated_data):
        instance = super().create(validated_data)

        custom_fields_data = self.initial_data.get("custom_fields")
        if custom_fields_data is not None and isinstance(custom_fields_data, list):
            self._save_custom_fields(instance, custom_fields_data)

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