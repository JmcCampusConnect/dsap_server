from rest_framework import serializers
from apps.departments.models import AcademicDepartment

class AcademicDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicDepartment
        fields = [
            'id',
            'code',
            'name',
            'degree',
            'branch',
            'type',
            'category',
            'hod_user_id',
            'status'
        ]
        read_only_fields = ['id', 'status']

    def validate_type(self, value):
        if value not in dict(AcademicDepartment.TYPE_CHOICES).keys():
            raise serializers.ValidationError("Invalid type. Must be 'UG' or 'PG'.")
        return value

    def validate_category(self, value):
        if value not in dict(AcademicDepartment.CATEGORY_CHOICES).keys():
            raise serializers.ValidationError("Invalid category. Must be 'AIDED', 'SFM', or 'SFW'.")
        return value
