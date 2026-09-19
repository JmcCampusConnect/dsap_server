from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from apps.departments.models import AcademicDepartment, ServiceDepartment
from ..models import User, Role
from ..role_constants import Roles


class ServiceDepartmentBriefSerializer(serializers.ModelSerializer):
    """Minimal service-department payload embedded into user responses."""

    class Meta:
        model = ServiceDepartment
        fields = ["id", "code", "name"]
        read_only_fields = fields


class AcademicDepartmentBriefSerializer(serializers.ModelSerializer):
    """Minimal academic-department payload embedded into user responses."""

    class Meta:
        model = AcademicDepartment
        fields = ["id", "code", "degree", "branch", "name"]
        read_only_fields = fields

class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role_id.name", read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
    password = serializers.CharField(write_only=True, required=False)
    
    # Writable FK ids (UI submits numeric ids).
    service_department_id = serializers.PrimaryKeyRelatedField(queryset=ServiceDepartment.objects.all(), required=False, allow_null=True)
    academic_department_id = serializers.PrimaryKeyRelatedField(queryset=AcademicDepartment.objects.all(),required=False, allow_null=True)
    
    # Read-only nested payloads for UI rendering without extra calls.
    service_department = ServiceDepartmentBriefSerializer(
        source="service_department_id", read_only=True
    )
    academic_department = AcademicDepartmentBriefSerializer(
        source="academic_department_id", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password", "role_id", "role_name", 
            "service_department_id", "service_department", "academic_department_id", "academic_department", "is_active", "created_at", "last_login"
        ]
        read_only_fields = ["id", "created_at", "last_login"]
    
    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_role_id(self, value):
        # Role assignment guard: role engine is the SSOT.
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return value
        if request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            # Dept admins can only create/edit Service Dept Staff.
            if value.name!= Roles.SERVICE_DEPT_STAFF:
                raise serializers.ValidationError("Service Dept Admin can only create/assign Service Dept Staff")
        # STAFF/STUDENT cannot assign roles
        if request.user.has_any_role([Roles.SERVICE_DEPT_STAFF, Roles.STUDENT, Roles.SUBJECT_TEACHING_STAFF]):
            raise serializers.ValidationError("Not allowed to assign roles")
        return value
    
    def validate(self, attrs):
        """
        Service Department scoping for create/update payloads.

        A SERVICE_DEPT_ADMIN must not be able to point a user at another
        department. We reject the payload explicitly (rather than silently
        rewriting it) so the caller gets a clear error.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return attrs

        if request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            admin_dept = request.user.service_department_id
            if admin_dept is None:
                raise serializers.ValidationError(
                    "Your account is not assigned to a service department."
                )

            provided_dept = attrs.get("service_department_id")
            if provided_dept is not None and provided_dept.id != admin_dept.id:
                raise serializers.ValidationError(
                    {
                        "service_department_id": (
                            "You cannot create or move users into another "
                            "service department."
                        )
                    }
                )

        return attrs
    
    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})

        request = self.context.get('request')
        if request and request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            # Force creator's department - never trust the client payload.
            validated_data['service_department_id'] = request.user.service_department_id

        return User.objects.create(password_hash=make_password(password), **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        request = self.context.get('request')
        if request and request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            # Defense in depth - validate() already rejected cross-dept moves.
            validated_data.pop('service_department_id', None)
            
            # Never allow a dept admin to promote a user above staff.
            role = validated_data.get("role_id")
            if role is not None and role.name != Roles.SERVICE_DEPT_STAFF:
                validated_data.pop('role_id', None)
                
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        if password:
            instance.password_hash = make_password(password)
        
        instance.save()
        return instance