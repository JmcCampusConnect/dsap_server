from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
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
    
class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model (used in UserViewSet)"""
    role_name = serializers.CharField(source='role_id.name', read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role_id', 'role_name', 'is_active', 'created_at', 'last_login']
        # 'password' is excluded for security; use create_user for writing

class RoleSerializer(serializers.ModelSerializer):
    """Serializer for the Role model (used in RoleViewSet)"""
    class Meta:
        model = Role
        fields = ['id', 'name']