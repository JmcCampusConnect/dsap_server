from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.hashers import check_password
from ..role_constants import get_accessible_menus
from ..models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends default JWT login to include username, role name, and accessible menus.
    """
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
                
        # ! User checking
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found!')
        
        # ! Password checking
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
            raise serializers.ValidationError(
                "Refresh token is required."
            )
        return value


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
    )