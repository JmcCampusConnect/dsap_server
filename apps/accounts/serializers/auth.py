from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.hashers import check_password
from ..role_constants import get_accessible_menus
from ..models import User
import time


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    remember = serializers.BooleanField(default=False, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        remember = attrs.get('remember', False)
        
        # ----- Single querry with select_related (efficient) -----
        try:
            user = User.objects.select_related('role_id', 'service_department_id', 'academic_department_id').get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found!')
        
        if not user.is_active:
            raise AuthenticationFailed('Account is deactivated!')
        
        if not check_password(password, user.password_hash):
            raise AuthenticationFailed('Incorrect password!')
        
        self.user = user
        
        refresh = self.get_token(user)
        refresh['remember_me'] = remember
        refresh['session_started_at'] = int(time.time())

        role_name = user.role_name or ""
        data = {
            "username": user.username,
            "role": role_name,
            "role_id": user.role_id.id if user.role_id else None,
            "service_department_id": getattr(user.service_department_id, 'id', None) if user.service_department_id else None,
            "menus": get_accessible_menus(role_name) if role_name else [],
            "refresh": str(refresh),
        }
        return data

class ValidateTokenSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()
    role_id = serializers.IntegerField(allow_null=True)
    service_department_id = serializers.IntegerField(allow_null=True)
    is_active = serializers.BooleanField()
    department = serializers.CharField(allow_null=True, allow_blank=True)
    menus = serializers.ListField(child=serializers.CharField())
    session_started_at = serializers.IntegerField(allow_null=True)

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Refresh token to blacklist")

    def validate_refresh(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value