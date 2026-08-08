from rest_framework import serializers
from apps.departments.models import ServiceDepartment
from apps.accounts.role_constants import Roles


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
        if value is None:
            return value
        
        # HOD must have SERVICE_DEPT_ADMIN role
        if value.role_id.name != Roles.SERVICE_DEPT_ADMIN:
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
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        
        # If user is NOT System Admin, restrict fields
        if user and not user.is_system_admin():
            # Dept Admin can only update name and hod_user_id (profile fields)
            allowed_fields = {'name', 'hod_user_id'}
            for field in list(validated_data.keys()):
                if field not in allowed_fields:
                    validated_data.pop(field, None)
                    
        # Proceed with update
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance