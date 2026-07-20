from django.contrib.auth.models import User
from rest_framework import serializers


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