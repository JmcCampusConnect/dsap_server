from rest_framework import serializers
from ..models import Role
from ..role_constants import Roles


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]

    def validate_name(self, value):
        if value not in Roles.all():
            raise serializers.ValidationError("Role is not supported.")
        return value