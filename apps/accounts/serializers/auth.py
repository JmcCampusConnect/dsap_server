from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from ..role_constants import get_accessible_menus


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends default JWT login to include username, role name, and accessible menus.
    """
    def validate(self, attrs):
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