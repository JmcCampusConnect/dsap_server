from rest_framework import serializers
from apps.services.models import Service, ServiceField
from apps.departments.models import ServiceDepartment


class ServiceDepartmentRefSerializer(serializers.ModelSerializer):
    """Minimal nested representation of the department inside Service responses."""

    class Meta:
        model = ServiceDepartment
        fields = ["id", "code", "name"]


class ServiceSerializer(serializers.ModelSerializer):
    """
    Full serializer for Service CRUD.

    Read  → returns nested `service_department` object {id, code, name}
    Write → accepts `service_department_id` as an integer FK
    """

    service_department = ServiceDepartmentRefSerializer(
        source="service_department_id",
        read_only=True,
    )

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
        ]
        read_only_fields = ["id", "code", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "service_department_id": {"write_only": True},
        }


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "service_id", "created_at", "updated_at"]

    def validate(self, data):
        instance = getattr(self, "instance", None)
        field_type = data.get("field_type", getattr(instance, "field_type", ""))
        options_json = data.get("options_json", getattr(instance, "options_json", None))

        if field_type in ["DROPDOWN", "RADIO", "CHECKBOX"]:
            if not options_json or not isinstance(options_json, list) or len(options_json) == 0:
                raise serializers.ValidationError(
                    {"options_json": f"options_json must be a non-empty list for {field_type} fields."}
                )
        else:
            # If type is not one of the above, options_json should be empty or null
            data["options_json"] = None

        return data
