from rest_framework import serializers
from apps.departments.models import AcademicDepartment


class AcademicDepartmentSerializer(serializers.ModelSerializer):

    stream = serializers.CharField(max_length=10)
    type = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(
        choices=AcademicDepartment.STATUS_CHOICES,
        read_only=True
    )
    
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

        allowed_streams = [
            choice[0] for choice in AcademicDepartment.STREAM_CHOICES
        ]

        matched = next(
            (
                stream_value
                for stream_value in allowed_streams
                if stream_value.lower() == val.lower()
            ),
            None
        )

        if matched:
            return matched

        raise serializers.ValidationError(
            f"Invalid Stream '{val}'. Allowed values: {', '.join(allowed_streams)}."
        )

    def validate_type(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Type is required.")

        val = str(value).strip()

        allowed_types = [choice[0] for choice in AcademicDepartment.TYPE_CHOICES]

        matched = next(
            (type_value for type_value in allowed_types
            if type_value.lower() == val.lower()),
            None
        )

        if matched:
            return matched

        raise serializers.ValidationError(
            f"Invalid Type '{val}'. Allowed values: {', '.join(allowed_types)}."
        )

    def validate_category(self, value):
        if not value or not str(value).strip():
            raise serializers.ValidationError("Category is required.")

        val = str(value).strip()

        allowed_categories = [
            choice[0] for choice in AcademicDepartment.CATEGORY_CHOICES
        ]

        matched = next(
            (category_value for category_value in allowed_categories
            if category_value.lower() == val.lower()),
            None
        )

        if matched:
            return matched

        raise serializers.ValidationError(
            f"Invalid Category '{val}'. Allowed values: {', '.join(allowed_categories)}."
        )

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
                    "code": ["Academic department already exists."]
                })
        return data
