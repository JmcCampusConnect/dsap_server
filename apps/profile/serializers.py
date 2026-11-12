from rest_framework import serializers

from apps.accounts.models import User
from apps.students.models import Student

# ---------------------------------------------------------------------
# Student composite
# ---------------------------------------------------------------------
class StudentPersonalSerializer(serializers.ModelSerializer):

    class Meta:
        model = Student
        fields = [
            "register_number",
            "name",
            "dob",
        ]
        read_only_fields = fields


class StudentAcademicSerializer(serializers.ModelSerializer):
    # Academic fields are derived from the linked department record;
    # expose them inlined so the client never needs a second request.
    department_id = serializers.IntegerField(
        source="academic_department_id.id", read_only=True
    )
    department_name = serializers.CharField(
        source="academic_department_id.name", read_only=True
    )
    type = serializers.CharField(
        source="academic_department_id.type", read_only=True
    )
    category = serializers.CharField(
        source="academic_department_id.category", read_only=True
    )

    class Meta:
        model = Student
        fields = [
            "department_id",
            "department_name",
            "type",
            "category",
            "stream",
            "year_of_admission",
            "section",
            "status",
        ]
        read_only_fields = fields


class StudentContactSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["mobile_number", "email"]
        read_only_fields = fields

    def get_email(self, obj):
        # email lives on the linked User row; select_related() in the
        # view prevents an extra query here.
        return obj.user_id.email if obj.user_id else None


# ---------------------------------------------------------------------
# Staff / Admin composite
# ---------------------------------------------------------------------
class StaffProfileSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role_id.name", read_only=True)
    service_department = serializers.SerializerMethodField()
    academic_department = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "role",
            "id",
            "username",
            "email",
            "service_department",
            "academic_department",
            "is_active",
            "last_login",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_service_department(self, obj):
        dept = obj.service_department_id
        if not dept:
            return None
        return {"id": dept.id, "code": dept.code, "name": dept.name}

    def get_academic_department(self, obj):
        dept = obj.academic_department_id
        if not dept:
            return None
        return {
            "id": dept.id,
            "code": dept.code,
            "degree": dept.degree,
            "branch": dept.branch,
            "name": dept.name,
        }