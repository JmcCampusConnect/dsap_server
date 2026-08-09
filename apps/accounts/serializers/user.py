from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from ..models import User, Role
from ..role_constants import Roles

class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role_id.name", read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), required=False)
    password = serializers.CharField(write_only=True, required=False)
    service_department_id = serializers.IntegerField(required=False, allow_null=True)
    academic_department_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password", "role_id", "role_name", 
            "service_department_id", "academic_department_id", "is_active", "created_at", "last_login"
        ]
        read_only_fields = ["id", "created_at", "last_login"]

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate_role_id(self, value):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return value
        # SERVICE_DEPT_ADMIN can only assign STAFF
        if request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            if value.name!= Roles.SERVICE_DEPT_STAFF:
                raise serializers.ValidationError("Dept Admin can only create Staff")
        # STAFF/STUDENT cannot assign roles
        if request.user.has_any_role([Roles.SERVICE_DEPT_STAFF, Roles.STUDENT, Roles.SUBJECT_TEACHING_STAFF]):
            raise serializers.ValidationError("Not allowed to assign roles")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        # Force dept scoping for DEPT_ADMIN
        request = self.context.get('request')
        if request and request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            validated_data['service_department_id'] = request.user.service_department_id

        return User.objects.create(password_hash=make_password(password), **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        # Prevent privilege escalation via service_department change
        request = self.context.get('request')
        if request and request.user.has_role(Roles.SERVICE_DEPT_ADMIN):
            validated_data.pop('service_department_id', None)
            if 'role_id' in validated_data and validated_data['role_id'].name!= Roles.SERVICE_DEPT_STAFF:
                validated_data.pop('role_id', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.password_hash = make_password(password)
        instance.save()
        return instance