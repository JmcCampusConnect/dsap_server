from rest_framework import serializers
from apps.departments.models import AcademicDepartment


class AcademicDepartmentSerializer(serializers.ModelSerializer):
    
    type = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=100)

    class Meta:
        model = AcademicDepartment
        fields = [
            "id", "code", "name", "degree", "branch", "type", "category", 
            "hod_user_id", "status", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_type(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Type cannot be empty.")
        return value

    def validate_category(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category cannot be empty.")
        return value

    def validate_code(self, value):
        return value.strip().upper()