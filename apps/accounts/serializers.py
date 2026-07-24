
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.hashers import make_password
from .role_constants import get_accessible_menus
from rest_framework import serializers
from .models import User, Role

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends default JWT login to include:
    - username
    - role name
    - accessible menus (from role_constants)
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Add basic user info
        data['username'] = user.username
        data['role'] = user.role_id.name if user.role_id else None

        # Include menu access list using their function
        if user.role_id:
            data['menus'] = get_accessible_menus(user.role_id.name)
        else:
            data['menus'] = []

        return data
    

# Serializer for logout to accept refresh token
class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Refresh token to blacklist")

    def validate_refresh(self, value):
        if not value:
            raise serializers.ValidationError("Refresh token is required.")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8
    )
    
    
class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model (used in UserViewSet)"""
    role_name = serializers.CharField(source='role_id.name', read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role_id', 'role_name', 'is_active', 'created_at', 'last_login']
        # 'password' is excluded for security; use create_user for writing
        read_only_fields = ["id","created_at","last_login"]

    def create(self, validated_data):
           password = validated_data.pop("password")

           if not password:
               raise serializers.ValidationError({
                   "password": "This field is required."
               })

           user = User.objects.create(
                password_hash=make_password(password),
                **validated_data
            )

           return user

    
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    

class RoleSerializer(serializers.ModelSerializer):
    """Serializer for the Role model (used in RoleViewSet)"""
    class Meta:
        model = Role
        fields = ['id', 'name']