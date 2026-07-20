from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .role_constants import get_accessible_menus
from rest_framework import serializers
# from .models import User, Role
from .models import Role
from django.contrib.auth.models import User

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
        data['role'] = user.role.name if user.role else None

        # Include menu access list using their function
        if user.role:
            data['menus'] = get_accessible_menus(user.role.name)
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
    password = serializers.CharField(write_only=True, required=False)
    status = serializers.SerializerMethodField()

    createdAt = serializers.DateTimeField(
        source="date_joined",
        read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "is_active", 
            "status",
            "createdAt",
        ]
        read_only_fields = ["id","status", "createdAt"]

    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"


    def validate_username(self, value):
        queryset = User.objects.filter(username=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Username already exists.")

        return value

    def create(self, validated_data):
        print(validated_data)   # <-- add this line

        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)  # Hashes the password
        user.save()

        return user

    def update(self, instance, validated_data):
        validated_data.pop("password", None)

        return super().update(instance, validated_data)

class RoleSerializer(serializers.ModelSerializer):
    """Serializer for the Role model (used in RoleViewSet)"""
    class Meta:
        model = Role
        fields = ['id', 'name']
