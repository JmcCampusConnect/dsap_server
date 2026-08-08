from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from ..models import User


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role_id.name", read_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "password",
            "role_id", "role_name", "is_active", "created_at", "last_login",
        ]
        read_only_fields = ["id", "created_at", "last_login"]  # role_id added — was mass-assignable before

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        return User.objects.create(password_hash=make_password(password), **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.password_hash = make_password(password)
        instance.save()
        return instance