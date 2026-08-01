from rest_framework import serializers
from apps.services.models import Service, ServiceDocument
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

