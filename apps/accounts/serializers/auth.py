from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.hashers import check_password
from ..role_constants import get_accessible_menus
from ..models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found!')
        
        if not check_password(password, user.password_hash):
            raise AuthenticationFailed('Incorrect password!')
        
        data = super().validate(attrs)
        user = self.user

        data["username"] = user.username
        data["role"] = user.role_id.name if user.role_id else None
        data["menus"] = (
            get_accessible_menus(user.role_id.name)
            if user.role_id else []
        )
        return data


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