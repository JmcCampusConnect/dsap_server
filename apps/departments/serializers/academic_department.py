from rest_framework import serializers
from apps.departments.models import AcademicDepartment


class AcademicDepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for AcademicDepartment model.

    Type and Category fields accept any non-empty string so that users can
    create new values via the frontend SearchableSelect component without
    being restricted to the initial MODEL-level choice constants.

    Validation enforces:
    - Non-empty strings for type and category
    - Code uniqueness (handled by model's unique=True constraint)
    - All required fields (handled by model's blank=False default)
    """

    # Explicitly declared as CharField so DRF never generates a ChoiceField
    # even if model-level choices are added in the future. This allows users
    # to create new type/category values via the frontend SearchableSelect.
    type = serializers.CharField(max_length=100)
    category = serializers.CharField(max_length=100)

    class Meta:
        model = AcademicDepartment
        fields = [
            "id",
            "code",
            "name",
            "degree",
            "branch",
            "type",
            "category",
            "hod_user_id",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_type(self, value):
        """Accept any non-empty string as type (supports user-created values)."""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Type cannot be empty.")
        return value

    def validate_category(self, value):
        """Accept any non-empty string as category (supports user-created values)."""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Category cannot be empty.")
        return value

    def validate_code(self, value):
        """Normalize code to uppercase and trim whitespace."""
        return value.strip().upper()
