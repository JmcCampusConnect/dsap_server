from rest_framework import serializers

from apps.departments.models import AcademicDepartment
from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    # Primary key field for the department
    academic_department_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicDepartment.objects.all(),
        required=False,
        allow_null=True
    )

    # Read‑only fields (show related info)
    user_id = serializers.IntegerField(source='user_id_id', read_only=True)
    academic_department_name = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            'id',
            'register_number',
            'name',
            'user_id',
            'academic_department_id',
            'academic_department_name',
            'batch_year',
            'dob',                     # renamed from date_of_birth
            'section',
            'stream',
            'mobile_number',
            'status',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user_id',
            'academic_department_name',
            'created_at',
            'updated_at',
        ]

    def get_academic_department_name(self, obj):
        department = getattr(obj, 'academic_department_id', None)
        if not department:
            return None
        parts = [department.code, department.degree, department.branch]
        return ' - '.join(part for part in parts if part)

    # Optional: if you want to ensure status is lowercase in output
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('status'):
            data['status'] = str(data['status']).lower()
        if data.get('stream') and str(data['stream']).upper() == 'AIDED':
            data['stream'] = 'Aided'
        return data