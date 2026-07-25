from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from .models import User, Role
from .role_constants import get_accessible_menus


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends default JWT login to include username, role name, and accessible menus.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        data['username'] = user.username
        data['role'] = user.role_id.name if user.role_id else None
        data['menus'] = get_accessible_menus(user.role_id.name) if user.role_id else []

        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Refresh token to blacklist")

    def validate_refresh(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role_id.name', read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role_id', 'role_name', 'is_active', 'created_at', 'last_login']
        read_only_fields = ['id', 'created_at', 'last_login']

    def create(self, validated_data):
        password = validated_data.pop('password', None)

        if not password:
            raise serializers.ValidationError({'password': 'This field is required.'})

        user = User.objects.create(
            password_hash=make_password(password),
            **validated_data
        )
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.password_hash = make_password(password)

        instance.save()
        return instance