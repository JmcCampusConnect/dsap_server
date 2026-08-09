from rest_framework import serializers
from apps.departments.models import AcademicDepartment


class AcademicDepartmentSerializer(serializers.ModelSerializer):
    
    type = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=100)

    class Meta:
        model = AcademicDepartment
        fields = [
            "id", "stream", "type", "category", "degree", "branch", "code", 
            "status", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]
        validators = []


    def validate_stream(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Stream is required.")
        val = str(value).strip()
        allowed_streams = [choice[0] for choice in AcademicDepartment.STREAM_CHOICES]
        # Match case-insensitively if possible
        matched = next((s for s in allowed_streams if s.lower() == val.lower()), None)
        if matched:
            return matched
        return val

    def validate_type(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Type cannot be empty.")
        return str(value).strip()

    def validate_category(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Category cannot be empty.")
        return str(value).strip()

    def validate_degree(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Degree cannot be empty.")
        return str(value).strip()

    def validate_branch(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Branch cannot be empty.")
        return str(value).strip()

    def validate_code(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Department Code cannot be empty.")
        return str(value).strip().upper()

    def validate(self, data):
        code = data.get('code') or getattr(self.instance, 'code', None)
        stream = data.get('stream') or getattr(self.instance, 'stream', None)

        if code and stream:
            qs = AcademicDepartment.objects.filter(code__iexact=code, stream__iexact=stream)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    "code": f"Department with Code '{code}' and Stream '{stream}' already exists."
                })

        return data