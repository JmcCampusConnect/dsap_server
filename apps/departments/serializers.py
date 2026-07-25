from rest_framework import serializers
from .models import ServiceDepartment


class ServiceDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceDepartment
        fields = [
            "id",
            "code",
            "name",
            "hod_user_id",
            "status",
        ]
        read_only_fields = ["id"]

    def validate_code(self, value):
        """
        Ensure department code is unique.
        """

        queryset = ServiceDepartment.objects.filter(code=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Department code already exists."
            )

        return value

    def validate_hod_user_id(self, value):
        """
        HOD must have SERVICE_DEPT_ADMIN role.
        """

        if value is None:
            return value

        if value.role_id.name != "SERVICE_DEPT_ADMIN":
            raise serializers.ValidationError(
                "Selected HOD must have SERVICE_DEPT_ADMIN role."
            )

        return value

    def create(self, validated_data):
        department = ServiceDepartment.objects.create(**validated_data)

        # TODO:
        # Auto-create the first Service once the
        # business rules (default code/name) are confirmed.

        return department