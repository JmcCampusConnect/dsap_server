from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from ..models import User


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(
        source="role_id.name",
        read_only=True,
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "role_id",
            "role_name",
            "is_active",
            "created_at",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "last_login",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None)

        if not password:
            raise serializers.ValidationError(
                {"password": "This field is required."}
            )

        return User.objects.create(
            password_hash=make_password(password),
            **validated_data
        )

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.password_hash = make_password(password)

        instance.save()
        return instance